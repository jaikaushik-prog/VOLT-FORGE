# Prepared questions; not sent

The electrical comparison can proceed without an external response. The unresolved
power-channel meaning blocks using that column as electrical power or heat.

Source release: https://zenodo.org/records/19052626,
`molicel_p45b_data.zip`, MD5 `0bd40f92dfabcea679900696cc2c0077`.
Member `MOLICEL_P45B_025degC_1C_Dch.csv`, SHA256
`41cef2d81d1a7c9fc139547d7a0a8d0961e0789f07aedac10a8a0009c21eaf5a`.
All source line references include the header as line 1.

1. **What exactly does Q_sim_W represent?** The two-page format guide describes
   signed cell power, negative on discharge. At source line 3,434, t=3,433.786 s,
   I_sim_A=-4.5000045068 A and V_sim_V=2.835515634 V, giving -12.759833132 W.
   Q_sim_W is +1.239714565 W. Please provide its defining equation, sign convention,
   units, and whether the guide or column name needs correction. If it is a heat
   quantity, specify included irreversible/reversible contributions and where
   temperature enters. We have not used this channel in voltage predictions.
2. **What preparation and cell identity apply to this 25 degC 1C discharge versus
   the base reference/pulse characterization?** Please identify the tested cell,
   preceding charge cutoff/CV taper/rest, capacity or SOC-origin corrections,
   and whether the observed end-of-discharge miss is expected for the base model.
   At the same final row, measurement is 2.499487735 V and disclosed V_sim_V is
   2.835515634 V. Our unadjusted reproduction gives 2.835526306 V. Across all
   3,433 samples, authors-versus-measurement RMSE is 35.85888 mV and
   ours-versus-authors RMSE is 0.01830 mV. These are full-record diagnostics;
   the validation workbook has not been opened and no claim about its particular
   scoring exclusions is made.

These questions request definitions and traceability, not permission to rescale
measurements or force agreement. No message, email or lab request was sent.
