# Generated frontend request/response examples

Generated from the executed A0/A1 demonstration, not handwritten response fixtures.
Revision/snapshot hashes bind this recorded demonstration; obtain current revision IDs from inspect before new edits.

The complete response corpus (including inherited/outdated and completed runs) is in `demo/examples/`.

## 04_validate_edit.json

Request:

```json
{
  "operation": "validate_edit",
  "arguments": {
    "variant_id": "A1",
    "edit": {
      "target": "connection",
      "id": "rail_p_1",
      "property": "resistance",
      "value": 0.0005,
      "unit": "ohm",
      "classification": "assumed",
      "source": "Predeclared manual hypothetical p1-p2 segment alternative; feasibility and resistance unmeasured"
    },
    "expected_revision": "rev_3b5cab3a673761e00fc59d725a04553590cbb583cc0fe9cf28233b88c1f2f828"
  }
}
```

Response:

```json
{
  "status": "ok",
  "result": {
    "valid": true,
    "physics_changed": true,
    "expected_revision": "rev_3b5cab3a673761e00fc59d725a04553590cbb583cc0fe9cf28233b88c1f2f828",
    "invalidated_run_ids": [],
    "classification": "exploratory edit; does not modify fitted artifacts",
    "warnings": [
      "Module accuracy unvalidated",
      "A user-declared measurement is not independently verified"
    ]
  }
}
```

## 10_series.json

Request:

```json
{
  "operation": "series",
  "arguments": {
    "variant_id": "A1",
    "run_id": "run_0002",
    "component_id": "cell_1",
    "limit": 2
  }
}
```

Response:

```json
{
  "status": "ok",
  "result": {
    "run_id": "run_0002",
    "variant_id": "A1",
    "component_id": "cell_1",
    "snapshot_id": "351fa6a36dac6561fbc042ce5eea2342dd7c9cd873defe48b0ebe6efb2bdab11",
    "execution_status": "completed",
    "freshness": "current",
    "units": {
      "time_s": "s",
      "current_A": "A",
      "voltage_V": "V",
      "soc": "fraction",
      "polarization_V": "V",
      "reference_V": "V",
      "positive_node_V": "V",
      "negative_node_V": "V",
      "R0_loss_W": "W",
      "R1_loss_W": "W"
    },
    "classification": "simulated",
    "total_samples": 1441,
    "offset": 0,
    "rows": [
      {
        "time_s": 0.0,
        "current_A": 4.526947362710232,
        "voltage_V": 3.80963787065498,
        "soc": 0.7,
        "polarization_V": 0.0,
        "reference_V": 3.92047309977826,
        "positive_node_V": 3.8096378706549774,
        "negative_node_V": -0.0,
        "R0_loss_W": 0.501745248175019,
        "R1_loss_W": 0.0
      },
      {
        "time_s": 0.25,
        "current_A": 4.5224823963170575,
        "voltage_V": 3.8092141467198815,
        "soc": 0.6999351629099759,
        "polarization_V": 0.0004726575072494,
        "reference_V": 3.920412715628432,
        "positive_node_V": 3.809214146719883,
        "negative_node_V": -0.0,
        "R0_loss_W": 0.5007559851285435,
        "R1_loss_W": 8.541042251251224e-06
      }
    ],
    "next_offset": 2
  }
}
```

## unsupported.json

Request:

```json
{
  "operation": "run_thermal",
  "arguments": {}
}
```

Response:

```json
{
  "status": "error",
  "error": {
    "code": "unsupported_request",
    "message": "Operation unavailable: run_thermal"
  }
}
```

## invalid_edit.json

Request:

```json
{
  "operation": "validate_edit",
  "arguments": {
    "variant_id": "A1",
    "edit": {
      "target": "connection",
      "id": "rail_p_1",
      "property": "resistance",
      "value": -0.001,
      "unit": "ohm",
      "classification": "assumed",
      "source": "Predeclared manual hypothetical p1-p2 segment alternative; feasibility and resistance unmeasured"
    },
    "expected_revision": "rev_f7cec9c49e8ef4d3802c055e803720b22d2b21008a733ab1fe1fc596808c1bcb"
  }
}
```

Response:

```json
{
  "status": "error",
  "error": {
    "code": "invalid_request",
    "message": "rail_p_1.resistance: below mathematical lower bound"
  }
}
```
