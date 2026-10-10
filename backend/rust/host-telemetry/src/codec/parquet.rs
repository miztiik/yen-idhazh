//! How do explicit host columns become truthful native Parquet bytes and return?

use crate::canonical_json::{rows_bytes, sha256};
use crate::contracts::file_envelope::{
    CandidateFileEnvelope, Compression, EnvelopeMetadata, Format, Writer,
};
use crate::contracts::host::{HostStoredRow, require};
use crate::ledger::schema::{ColumnType, HOST_COLUMNS};
use crate::{Result, Validate};
use arrow_array::{Array, ArrayRef, Float64Array, Int64Array, RecordBatch, StringArray};
use arrow_schema::{DataType, Field, Schema};
use bytes::Bytes;
use parquet::arrow::{ArrowWriter, arrow_reader::ParquetRecordBatchReaderBuilder};
use parquet::basic::{Compression as NativeCompression, Encoding, ZstdLevel};
use parquet::file::metadata::KeyValue;
use parquet::file::properties::{EnabledStatistics, WriterProperties, WriterVersion};
use std::sync::Arc;

pub fn engine_version() -> &'static str {
    parquet::file::properties::DEFAULT_CREATED_BY
        .strip_prefix("parquet-rs version ")
        .expect("native engine version")
}
fn schema() -> Schema {
    Schema::new(
        HOST_COLUMNS
            .iter()
            .map(|column| {
                Field::new(
                    column.name,
                    match column.r#type {
                        ColumnType::String => DataType::Utf8,
                        ColumnType::Int64 => DataType::Int64,
                        ColumnType::Float64 => DataType::Float64,
                    },
                    column.nullable,
                )
            })
            .collect::<Vec<_>>(),
    )
}
fn batch(rows: &[HostStoredRow]) -> Result<RecordBatch> {
    let values = rows
        .iter()
        .map(|row| {
            row.validate()?;
            serde_json::to_value(row).map_err(|e| e.to_string())
        })
        .collect::<Result<Vec<_>>>()?;
    let mut arrays: Vec<ArrayRef> = Vec::new();
    for column in HOST_COLUMNS {
        let cells = values
            .iter()
            .map(|row| &row[column.name])
            .collect::<Vec<_>>();
        let array: ArrayRef = match column.r#type {
            ColumnType::String => Arc::new(StringArray::from(
                cells.iter().map(|v| v.as_str()).collect::<Vec<_>>(),
            )),
            ColumnType::Int64 => Arc::new(Int64Array::from(
                cells.iter().map(|v| v.as_i64()).collect::<Vec<_>>(),
            )),
            ColumnType::Float64 => Arc::new(Float64Array::from(
                cells.iter().map(|v| v.as_f64()).collect::<Vec<_>>(),
            )),
        };
        arrays.push(array);
    }
    RecordBatch::try_new(Arc::new(schema()), arrays).map_err(|e| e.to_string())
}
pub fn render(rows: &[HostStoredRow], envelope: &CandidateFileEnvelope) -> Result<Vec<u8>> {
    envelope.validate_container(Format::Parquet)?;
    require(
        envelope.writer == Writer::RustParquet && envelope.writer_version == engine_version(),
        "Parquet render needs truthful native writer/version",
    )?;
    envelope.validate_rows(rows)?;
    let batch = batch(rows)?;
    require(
        sha256(&rows_bytes(rows)?) == envelope.content_sha256,
        "Parquet content hash mismatch",
    )?;
    let metadata = serde_json::to_value(envelope.metadata()?).map_err(|e| e.to_string())?;
    let metadata = metadata
        .as_object()
        .ok_or("metadata object")?
        .iter()
        .map(|(k, v)| {
            Ok(KeyValue {
                key: k.clone(),
                value: Some(v.as_str().ok_or("metadata string")?.to_owned()),
            })
        })
        .collect::<Result<Vec<_>>>()?;
    let compression = match envelope.compression {
        Compression::None => NativeCompression::UNCOMPRESSED,
        Compression::Snappy => NativeCompression::SNAPPY,
        Compression::Zstd => NativeCompression::ZSTD(ZstdLevel::default()),
    };
    // The bounded Python admission reads V1, flat scalar, single-row pages.
    // Dictionary encoding is deliberately off; this is the plain supported profile.
    let properties = WriterProperties::builder()
        .set_writer_version(WriterVersion::PARQUET_1_0)
        .set_compression(compression)
        .set_dictionary_enabled(false)
        .set_encoding(Encoding::PLAIN)
        .set_statistics_enabled(EnabledStatistics::Chunk)
        .set_offset_index_disabled(true)
        .set_max_row_group_row_count(Some(1))
        .set_key_value_metadata(Some(metadata))
        .build();
    let mut bytes = Vec::new();
    {
        let mut writer = ArrowWriter::try_new(&mut bytes, Arc::new(schema()), Some(properties))
            .map_err(|e| e.to_string())?;
        if !rows.is_empty() {
            writer.write(&batch).map_err(|e| e.to_string())?;
        }
        writer.close().map_err(|e| e.to_string())?;
    }
    Ok(bytes)
}
pub fn read(bytes: &[u8], max_bytes: usize) -> Result<(CandidateFileEnvelope, Vec<HostStoredRow>)> {
    require(bytes.len() <= max_bytes, "Parquet exceeds read bound")?;
    let builder = ParquetRecordBatchReaderBuilder::try_new(Bytes::copy_from_slice(bytes))
        .map_err(|e| e.to_string())?;
    require(
        builder.schema().fields() == schema().fields(),
        "Parquet schema/order/nullability mismatch",
    )?;
    let entries = builder
        .metadata()
        .file_metadata()
        .key_value_metadata()
        .ok_or("missing footer metadata")?;
    let mut metadata = serde_json::Map::new();
    for entry in entries {
        if entry.key == "ARROW:schema" {
            continue;
        }
        require(
            metadata
                .insert(
                    entry.key.clone(),
                    serde_json::Value::String(entry.value.clone().ok_or("missing metadata value")?),
                )
                .is_none(),
            "duplicate footer key",
        )?;
    }
    let metadata: EnvelopeMetadata =
        serde_json::from_value(serde_json::Value::Object(metadata)).map_err(|e| e.to_string())?;
    let envelope = metadata.envelope()?;
    envelope.validate_container(Format::Parquet)?;
    for group in builder.metadata().row_groups() {
        for chunk in group.columns() {
            require(
                matches!(
                    (envelope.compression, chunk.compression()),
                    (Compression::None, NativeCompression::UNCOMPRESSED)
                        | (Compression::Snappy, NativeCompression::SNAPPY)
                        | (Compression::Zstd, NativeCompression::ZSTD(_))
                ),
                "Parquet compression/footer mismatch",
            )?;
        }
    }
    if envelope.writer == Writer::RustParquet {
        require(
            builder.metadata().file_metadata().created_by()
                == Some(format!("parquet-rs version {}", envelope.writer_version).as_str()),
            "untruthful native created_by",
        )?;
    }
    let mut rows = Vec::new();
    let reader = builder
        .with_batch_size(1)
        .build()
        .map_err(|e| e.to_string())?;
    for batch in reader {
        let batch = batch.map_err(|e| e.to_string())?;
        for index in 0..batch.num_rows() {
            let mut row = serde_json::Map::new();
            for (column, array) in HOST_COLUMNS.iter().zip(batch.columns()) {
                let value = if array.is_null(index) {
                    serde_json::Value::Null
                } else {
                    match column.r#type {
                        ColumnType::String => serde_json::json!(
                            array
                                .as_any()
                                .downcast_ref::<StringArray>()
                                .ok_or("string column")?
                                .value(index)
                        ),
                        ColumnType::Int64 => serde_json::json!(
                            array
                                .as_any()
                                .downcast_ref::<Int64Array>()
                                .ok_or("int64 column")?
                                .value(index)
                        ),
                        ColumnType::Float64 => {
                            let value = array
                                .as_any()
                                .downcast_ref::<Float64Array>()
                                .ok_or("float64 column")?
                                .value(index);
                            require(value.is_finite(), "Parquet contains nonfinite float")?;
                            serde_json::json!(value)
                        }
                    }
                };
                row.insert(column.name.to_owned(), value);
            }
            rows.push(
                serde_json::from_value(serde_json::Value::Object(row))
                    .map_err(|e| e.to_string())?,
            );
        }
    }
    require(
        sha256(&rows_bytes(&rows)?) == envelope.content_sha256,
        "Parquet content hash mismatch",
    )?;
    envelope.validate_rows(&rows)?;
    Ok((envelope, rows))
}
