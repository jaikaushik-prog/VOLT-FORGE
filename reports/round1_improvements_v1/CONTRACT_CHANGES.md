# V4.1 interface additions and corrected meanings

These additions retain the existing `/api/studio` transport and saved-run format. Old records remain immutable. No new service or frontend framework is introduced.

## Recover a draft without a stale overwrite

POST `/api/studio`, with the existing session token header:

```json
{
  "operation": "save_copy",
  "arguments": {
    "graph": "the complete current graph object",
    "settings": "the complete current settings object",
    "name": "Recovered design",
    "source_design_id": "the original design ID, when recovering in the same workspace",
    "source_version": 2
  }
}
```

The strings describing graph/settings above are placeholders for the existing JSON objects, not valid executable payloads. Success returns the existing document response with a **new** ID, version 1, no inherited test history, validated graph/settings and `origin.kind = recovered_draft`. A stale source version is permitted because the operation never overwrites that source. Origin records the supplied source version and the actual saved source version separately. Invalid data produces the existing error envelope before a document is committed.

Imported `voltforge.design-backup/1` JSON must omit source ID/version when invoking this operation: IDs from a different workspace cannot establish lineage. It creates a new editable design, not a restored result history. Unfinished field text is carried in the backup as notes and is not treated as physical input. Experiment ZIPs remain report/replay packages; this change does not add ZIP-to-project import.

## Runtime and AI metadata

Catalog responses add `runtime`:

```json
{
  "persistence": "local_workspace",
  "project_import_supported": false,
  "design_draft_import_supported": true,
  "description": "Saved by this workspace on this computer."
}
```

The public worker returns `persistence = browser_session` and explicitly describes its temporary lifetime. A local workspace save and a browser-session save must not share a durability promise.

`copilot.status()` adds `connection_verified: false` and an `availability_basis`: `provider_executable_present`, `server_configuration` or `not_configured`. Finding an executable/key configuration does not verify authentication or a successful provider response. The public endpoint's GET returns only configuration availability and connection status; it never invokes a provider or returns a key. The optional lookup times out after two seconds, so it cannot indefinitely block manual startup. No provider inference was performed while implementing or testing this change.

## Physical result semantics

- `summary.operating_limit_coverage` contains per-cell actual current directions, missing operating-limit fields, their basis and completeness. Sizing cannot qualify a result whose applicable limits are incomplete. Application targets and reference-curve support remain different concepts.
- `summary.charging.version = voltforge.pack-charge/2` identifies terminal charge accounting. `received_charge_Ah` and `delivered_charge_Ah` are gross quantities; `net_charge_gained_Ah` is their difference. `per_cell_charge_gained_Ah` remains separate. The compatibility alias `charge_gained_Ah` means net pack Ah only in this version. Unversioned historical quantities are labelled aggregate cell Ah rather than silently reinterpreted.
- `summary.link_checks.links[].peak_current_A` and current density can be null. `current_status` and `current_reason` explain an uncomputed ideal-link current. Zero resistance/loss does not imply zero current.
- Parts remain priced candidates. Converter lines add `selection = candidate` and `compatibility.status` of `conditional`, `incompatible` or `not_assessed`, with reasons/conditions. Even a conditional candidate retains unverified battery-current, charge, contact and protection details. A changed current profile cannot inherit a power-based board screening from a stale preset label.
- `parts.cell_subtotals` and `cell_cost_complete` support the explicitly cell-only 4/3/2 comparison. Currencies remain separate; missing prices are not zero.

## Saved-result ownership

Use a selected test's `graph`, `settings`, `model_cards`, model/software identities and returned comparison flags for every result explanation. Missing historical cards stay unavailable. Do not substitute the current catalog's model description. Pure screen-position changes retain existing physics invalidation behavior.

The persistent sample table uses exact saved samples and identifies before/after event sides; it does not interpolate a new physical result. Mouse, touch and keyboard controls reference the same index. Comparison exposes model, software, requirements, preparation, thermal assumptions and served-duration differences before performance deltas.

These contracts describe simulation software. They do not establish measured module accuracy, compatible hardware protection or a calibrated prediction interval.
