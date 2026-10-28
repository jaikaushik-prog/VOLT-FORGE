# Custom cell import

Enter a name, capacity in Ah, nominal voltage in V and DC resistance in milliohms in the app. Without a voltage reference this is a constant-voltage resistive estimate, not a fitted dynamic battery model. A basic four-field cell uses example cylindrical-cell thermal properties: 70 J/K heat capacity and 0.15 W/K cooling conductance. These are declared assumptions, not measurements of the custom cell. Choose Electrical results only or set `thermal_defaults: null` to disable this estimate. Without operating limits, no component clearance is established.

For a measured voltage curve, import a UTF-8 CSV with exactly these columns in this order. Charge must increase; values must be finite. These are illustrative coordinates, not measured data:

```csv
soc_pct,voltage_V
10,3.2
50,3.6
90,4.1
```

CSV capacity, resistance and source are taken from the form. Use 2 to 2,048 rows. The current model uses one declared DC resistance across this curve.

A JSON basic model uses this structure. The numbers below are an example, not validated parameters:

```json
{
  "version": "voltforge.custom-cell/1",
  "kind": "basic_resistive/1",
  "name": "My cell",
  "capacity_Ah": 2.0,
  "nominal_voltage_V": 3.7,
  "resistance_mohm": 20,
  "source": {"url": "", "description": "My measurement source"},
  "operating_limits": {},
  "thermal_defaults": null
}
```

An optional `reference` has equal-length `soc` (0 to 1) and `voltage_V` arrays. Optional `thermal_defaults` requires both `heat_capacity_J_K` and `ambient_conductance_W_K`. Optional operating limits are `voltage_V: [minimum, maximum]`, `max_charge_A`, `max_discharge_A`, `charge_temperature_C: [minimum, maximum]`, and `discharge_temperature_C: [minimum, maximum]`. Values are user-provided and remain unassessed.

For an advanced lookup model use `kind: "temperature_dependent_ecm/1"`, `name`, `capacity_Ah`, `source`, and these arrays:

- `soc`: strictly increasing fractions, 2 to 256 coordinates.
- `temperature_C`: strictly increasing temperatures, 2 to 32 coordinates.
- `nrc`: integer 0 to 3.
- `ocv_V` and `r0_ohm`: `[temperature][soc]` tables.
- `r_ohm` and `tau_s`: `[temperature][soc][branch]` tables. All branch resistances and time constants must be positive. With zero branches each branch list is empty.
- Optional `entropy`: `soc` and `dOCV_dT_V_K` arrays covering the electrical SOC range. This coefficient determines reversible heat and needs its own source evidence.

Do not include `nominal_voltage_V`, `resistance_mohm` or `reference` for an advanced model. Use the explicit arrays. The solver interpolates within supplied coordinates and stops at their edges. It does not extrapolate data. Files may not exceed 120 KB and must contain data only. Each saved version receives a new identity; existing tests keep their original definition.
