//! Which sorted ASCII JSON bytes define row content identity?

use crate::Result;
use serde::Serialize;
use serde_json::Value;
use sha2::{Digest, Sha256};

pub fn float_text(value: f64) -> Result<String> {
    if !value.is_finite() {
        return Err("canonical JSON refuses nonfinite floats".to_owned());
    }
    if value == 0.0 {
        return Ok(if value.is_sign_negative() {
            "-0.0"
        } else {
            "0.0"
        }
        .to_owned());
    }
    // Ryu supplies shortest round-trip digits. Python selects fixed notation at
    // exponents -4..15, and pads signed scientific exponents to two digits.
    let mut buffer = ryu::Buffer::new();
    let raw = buffer.format_finite(value);
    let (sign, raw) = if let Some(rest) = raw.strip_prefix('-') {
        ("-", rest)
    } else {
        ("", raw)
    };
    let (mantissa, extra) = raw.split_once('e').map_or((raw, 0), |(m, e)| {
        (m, e.parse::<i32>().expect("Ryu exponent"))
    });
    let before = mantissa.find('.').unwrap_or(mantissa.len()) as i32;
    let all = mantissa.replace('.', "");
    let first = all.find(|c| c != '0').expect("nonzero float");
    let mut digits = all[first..].trim_end_matches('0').to_owned();
    let exponent = before - first as i32 - 1 + extra;
    if !(-4..16).contains(&exponent) {
        if digits.len() > 1 {
            digits.insert(1, '.');
        }
        Ok(format!(
            "{sign}{digits}e{}{abs:02}",
            if exponent < 0 { "-" } else { "+" },
            abs = exponent.abs()
        ))
    } else {
        let point = exponent + 1;
        let body = if point <= 0 {
            format!("0.{}{digits}", "0".repeat((-point) as usize))
        } else if point as usize >= digits.len() {
            format!("{digits}{}.0", "0".repeat(point as usize - digits.len()))
        } else {
            digits.insert(point as usize, '.');
            digits
        };
        Ok(format!("{sign}{body}"))
    }
}

fn string(value: &str, out: &mut String) {
    out.push('"');
    for c in value.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\u{08}' => out.push_str("\\b"),
            '\u{0c}' => out.push_str("\\f"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{20}'..='\u{7e}' => out.push(c),
            _ => {
                use std::fmt::Write;
                for unit in c.encode_utf16(&mut [0; 2]) {
                    write!(out, "\\u{unit:04x}").expect("String write");
                }
            }
        }
    }
    out.push('"');
}
fn encode(value: &Value, out: &mut String) -> Result<()> {
    match value {
        Value::Null => out.push_str("null"),
        Value::Bool(v) => out.push_str(if *v { "true" } else { "false" }),
        Value::Number(v) => {
            if v.is_f64() {
                out.push_str(&float_text(v.as_f64().ok_or("invalid float")?)?);
            } else {
                out.push_str(&v.to_string());
            }
        }
        Value::String(v) => string(v, out),
        Value::Array(values) => {
            out.push('[');
            for (i, v) in values.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                encode(v, out)?;
            }
            out.push(']');
        }
        Value::Object(values) => {
            out.push('{');
            let mut keys = values.keys().collect::<Vec<_>>();
            keys.sort();
            for (i, key) in keys.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                string(key, out);
                out.push(':');
                encode(&values[*key], out)?;
            }
            out.push('}');
        }
    }
    Ok(())
}
pub fn object_bytes<T: Serialize>(value: &T) -> Result<Vec<u8>> {
    let value = serde_json::to_value(finite::Finite(value)).map_err(|e| e.to_string())?;
    let mut result = String::new();
    encode(&value, &mut result)?;
    Ok(result.into_bytes())
}
pub fn row_line<T: Serialize>(value: &T) -> Result<Vec<u8>> {
    let mut result = object_bytes(value)?;
    result.push(b'\n');
    Ok(result)
}
pub fn rows_bytes<T: Serialize>(rows: &[T]) -> Result<Vec<u8>> {
    let mut result = Vec::new();
    for row in rows {
        result.extend(row_line(row)?);
    }
    Ok(result)
}
pub fn sha256(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

// serde_json intentionally turns NaN into null. Guard floats recursively before
// its maintained value serializer runs, so canonical null is never a lost number.
mod finite {
    use serde::{Serialize, Serializer, ser};
    pub(super) struct Finite<'a, T: ?Sized>(pub &'a T);
    struct Checked<S>(S);
    struct Compound<C>(C);
    impl<T: ?Sized + Serialize> Serialize for Finite<'_, T> {
        fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
            self.0.serialize(Checked(serializer))
        }
    }
    macro_rules! scalar {
        ($($name:ident:$ty:ty),*$(,)?) => {$(
            fn $name(self, value:$ty)->Result<Self::Ok,Self::Error>{self.0.$name(value)}
        )*};
    }
    impl<S: Serializer> Serializer for Checked<S> {
        type Ok = S::Ok;
        type Error = S::Error;
        type SerializeSeq = Compound<S::SerializeSeq>;
        type SerializeTuple = Compound<S::SerializeTuple>;
        type SerializeTupleStruct = Compound<S::SerializeTupleStruct>;
        type SerializeTupleVariant = Compound<S::SerializeTupleVariant>;
        type SerializeMap = Compound<S::SerializeMap>;
        type SerializeStruct = Compound<S::SerializeStruct>;
        type SerializeStructVariant = Compound<S::SerializeStructVariant>;
        scalar!(serialize_bool:bool,serialize_i8:i8,serialize_i16:i16,serialize_i32:i32,
            serialize_i64:i64,serialize_i128:i128,serialize_u8:u8,serialize_u16:u16,
            serialize_u32:u32,serialize_u64:u64,serialize_u128:u128,serialize_char:char,
            serialize_str:&str,serialize_bytes:&[u8]);
        fn serialize_f32(self, value: f32) -> Result<Self::Ok, Self::Error> {
            if !value.is_finite() {
                return Err(ser::Error::custom("nonfinite canonical float"));
            }
            self.0.serialize_f32(value)
        }
        fn serialize_f64(self, value: f64) -> Result<Self::Ok, Self::Error> {
            if !value.is_finite() {
                return Err(ser::Error::custom("nonfinite canonical float"));
            }
            self.0.serialize_f64(value)
        }
        fn serialize_none(self) -> Result<Self::Ok, Self::Error> {
            self.0.serialize_none()
        }
        fn serialize_some<T: ?Sized + Serialize>(self, value: &T) -> Result<Self::Ok, Self::Error> {
            self.0.serialize_some(&Finite(value))
        }
        fn serialize_unit(self) -> Result<Self::Ok, Self::Error> {
            self.0.serialize_unit()
        }
        fn serialize_unit_struct(self, name: &'static str) -> Result<Self::Ok, Self::Error> {
            self.0.serialize_unit_struct(name)
        }
        fn serialize_unit_variant(
            self,
            name: &'static str,
            index: u32,
            variant: &'static str,
        ) -> Result<Self::Ok, Self::Error> {
            self.0.serialize_unit_variant(name, index, variant)
        }
        fn serialize_newtype_struct<T: ?Sized + Serialize>(
            self,
            name: &'static str,
            value: &T,
        ) -> Result<Self::Ok, Self::Error> {
            self.0.serialize_newtype_struct(name, &Finite(value))
        }
        fn serialize_newtype_variant<T: ?Sized + Serialize>(
            self,
            name: &'static str,
            index: u32,
            variant: &'static str,
            value: &T,
        ) -> Result<Self::Ok, Self::Error> {
            self.0
                .serialize_newtype_variant(name, index, variant, &Finite(value))
        }
        fn serialize_seq(self, len: Option<usize>) -> Result<Self::SerializeSeq, Self::Error> {
            self.0.serialize_seq(len).map(Compound)
        }
        fn serialize_tuple(self, len: usize) -> Result<Self::SerializeTuple, Self::Error> {
            self.0.serialize_tuple(len).map(Compound)
        }
        fn serialize_tuple_struct(
            self,
            name: &'static str,
            len: usize,
        ) -> Result<Self::SerializeTupleStruct, Self::Error> {
            self.0.serialize_tuple_struct(name, len).map(Compound)
        }
        fn serialize_tuple_variant(
            self,
            name: &'static str,
            index: u32,
            variant: &'static str,
            len: usize,
        ) -> Result<Self::SerializeTupleVariant, Self::Error> {
            self.0
                .serialize_tuple_variant(name, index, variant, len)
                .map(Compound)
        }
        fn serialize_map(self, len: Option<usize>) -> Result<Self::SerializeMap, Self::Error> {
            self.0.serialize_map(len).map(Compound)
        }
        fn serialize_struct(
            self,
            name: &'static str,
            len: usize,
        ) -> Result<Self::SerializeStruct, Self::Error> {
            self.0.serialize_struct(name, len).map(Compound)
        }
        fn serialize_struct_variant(
            self,
            name: &'static str,
            index: u32,
            variant: &'static str,
            len: usize,
        ) -> Result<Self::SerializeStructVariant, Self::Error> {
            self.0
                .serialize_struct_variant(name, index, variant, len)
                .map(Compound)
        }
        fn is_human_readable(&self) -> bool {
            self.0.is_human_readable()
        }
    }
    macro_rules! sequence {
        ($trait:ident,$method:ident) => {
            impl<C: ser::$trait> ser::$trait for Compound<C> {
                type Ok = C::Ok;
                type Error = C::Error;
                fn $method<T: ?Sized + Serialize>(&mut self, value: &T) -> Result<(), Self::Error> {
                    self.0.$method(&Finite(value))
                }
                fn end(self) -> Result<Self::Ok, Self::Error> {
                    self.0.end()
                }
            }
        };
    }
    sequence!(SerializeSeq, serialize_element);
    sequence!(SerializeTuple, serialize_element);
    sequence!(SerializeTupleStruct, serialize_field);
    sequence!(SerializeTupleVariant, serialize_field);
    macro_rules! structure {
        ($trait:ident) => {
            impl<C: ser::$trait> ser::$trait for Compound<C> {
                type Ok = C::Ok;
                type Error = C::Error;
                fn serialize_field<T: ?Sized + Serialize>(
                    &mut self,
                    key: &'static str,
                    value: &T,
                ) -> Result<(), Self::Error> {
                    self.0.serialize_field(key, &Finite(value))
                }
                fn skip_field(&mut self, key: &'static str) -> Result<(), Self::Error> {
                    self.0.skip_field(key)
                }
                fn end(self) -> Result<Self::Ok, Self::Error> {
                    self.0.end()
                }
            }
        };
    }
    structure!(SerializeStruct);
    structure!(SerializeStructVariant);
    impl<C: ser::SerializeMap> ser::SerializeMap for Compound<C> {
        type Ok = C::Ok;
        type Error = C::Error;
        fn serialize_key<T: ?Sized + Serialize>(&mut self, key: &T) -> Result<(), Self::Error> {
            self.0.serialize_key(&Finite(key))
        }
        fn serialize_value<T: ?Sized + Serialize>(&mut self, value: &T) -> Result<(), Self::Error> {
            self.0.serialize_value(&Finite(value))
        }
        fn serialize_entry<K: ?Sized + Serialize, V: ?Sized + Serialize>(
            &mut self,
            key: &K,
            value: &V,
        ) -> Result<(), Self::Error> {
            self.0.serialize_entry(&Finite(key), &Finite(value))
        }
        fn end(self) -> Result<Self::Ok, Self::Error> {
            self.0.end()
        }
    }
}
