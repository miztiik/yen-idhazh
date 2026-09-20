// Generated from `backend/idhazh/contracts/icon_manifest.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/** What was generated, from where, under which licence. */
export interface IconManifest {
	version?: string;

	source: string;

	licence: string;

	icons: string[];
}
