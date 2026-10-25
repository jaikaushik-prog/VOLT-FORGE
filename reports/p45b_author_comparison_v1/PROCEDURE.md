# Predeclared comparison with authors' outputs for the used discharge family

This procedure is declared before converting any numeric author-output fields.
The measured values in this family are already used development evidence. The
purpose is to locate differences between implementations, not tune a model or
obtain fresh independent validation.

## Access and preservation

Read the six author-output columns in exactly
`MOLICEL_P45B_025degC_1C_Dch.csv`: `I_sim_A`, `V_sim_V`, `SOC_sim`, `E_OCV_V`,
`T_sim_degC`, `Q_sim_W`. Retain their author-prediction labels, original units,
source lines and hash. Q_sim_W is signed electrical cell power, not heat.
Reuse the unchanged base parameter table and the completed reproduction's
`run_002/primary.csv`. Do not replace any measured input with an author value.
Do not open another archive member, the charge-optimized table or validation
workbook. Preserve all earlier runs, source files, frozen LG models and allocations.

## Comparisons fixed before access

1. Join strictly by source line and timestamp to the saved primary trace. Verify
   the experimental channels match exactly; do not sort, shift or interpolate to
   improve agreement. The released author outputs are already on the experimental
   time grid according to the format guide.
2. Report voltage errors for our prediction versus measurement, author prediction
   versus measurement, and ours versus author. Give full available and identical
   common-sample masks, sample/time RMSE and bias, maximum error, counts and covered
   durations. Also report the previously declared nominal-SOC bins using **our
   unchanged SOC**. No new accuracy target or operating domain is selected here.
3. Compare initial/final and full-trace SOC, current and temperature. Independently
   integrate each current using 4.5 Ah and left-held/linear conventions, anchored
   to its own first disclosed SOC. Report residuals against SOC_sim without fitting
   a different capacity, SOC origin or time shift. Author SOC is simulated, not
   an observed calibration target.
4. Query the unchanged 25 degC discharge-reference branch at our SOC and author
   SOC where each is inside the table and temperature is applicable. No extension.
   Compare the latter with E_OCV_V. This is a consistency diagnostic for the paper's
   h=-1 discharge convention, not an inferred equilibrium OCV measurement.
5. On rows where all terms are defined, decompose ours-minus-author terminal
   voltage into (a) reference difference, (b) series-ohmic difference using the
   respective disclosed currents and SOC lookups, and (c) remaining polarization
   difference. The author's polarization total is an **algebraic inferred remainder**
   `V_sim - E_OCV - I_sim*R0(SOC_sim)`, not measured or individually disclosed RC
   states. Verify the three contributions sum to the voltage difference. Also
   split the reference difference into SOC-coordinate and same-SOC branch terms.
6. Check the documented signed-power identity `Q_sim_W = I_sim_A*V_sim_V` and
   report discrepancies without repairing any channels. Interpolation can itself
   affect identities; these are diagnostics, not calibration certificates.

Missing/NaN author values remain missing and are counted. Reject infinities,
malformed values, duplicate/backwards timestamps, source mismatch or ambiguous
headers. Time metrics use only adjacent finite samples and never bridge a gap
or missing point. No voltage truncation is used for the primary comparison; show
the measured/ours/author 2.5 V protocol crossings separately. This is a cell-test
protocol value, not a configured device requirement.

Produce a machine-readable comparison, voltage/residual and state/reference
plots, and a short decision separating confirmed differences from hypotheses.
Keep the electrical models and simulation settings unchanged. If implementation
or source inconsistency is found, record it and propose a bounded follow-up;
do not adjust the model to match the authors or the measurements in this stage.
Stop after this comparison and its preservation checks. Module validation and
application voltage decisions remain separate, unsupported workstreams.
