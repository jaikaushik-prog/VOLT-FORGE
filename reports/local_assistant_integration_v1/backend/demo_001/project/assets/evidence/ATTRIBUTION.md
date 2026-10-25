# Sources and transformations

Access checked 24 October 2026.

- Piombo, G.; Fasolato, S.; Heymer, R.; Hidalgo, M. F.; Faraji Niri, M.;
  Raimondo, D. M.; Marco, J.; Onori, S. (2024).
  [Full factorial design of experiments dataset for parallel-connected lithium-ion cells imbalanced performance investigation](https://data.mendeley.com/datasets/zh58byr53c/2).
  Mendeley Data, v2. DOI **10.17632/zh58byr53c.2**.
  [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/)
  is the licence specified on the official record. The user retrieved the ZIP;
  the pipeline records local cryptographic identity, not a publisher signature.
- Piombo et al. (2024), *Data in Brief* 53, 110227.
  DOI [10.1016/j.dib.2024.110227](https://doi.org/10.1016/j.dib.2024.110227).
  [Author-hosted paper](https://pangea.stanford.edu/ERE/pdf/OnoriPDF/Journals/91.pdf).
  Tables 2-5 and sections 3/3.1 establish protocols, nominal conditions, cell
  identities and channels. The paper cites dataset v1; the requested record is v2.
  The paper itself is CC BY 4.0. The NMC rows transcribed into
  `configs/nmc_article_table5.csv` retain the published Y1 contradiction.
- Fasolato, S.; Allam, A.; Onori, S.; Raimondo, D. M. (2025), *Journal of
  Energy Storage* 129, 116942, DOI
  [10.1016/j.est.2025.116942](https://doi.org/10.1016/j.est.2025.116942).
  [Author-hosted paper](https://pangea.stanford.edu/ERE/pdf/OnoriPDF/Journals/109.pdf).
  Sections 2.1-2.2, Figure 2 and equation (1) inform the proposed shared-rail
  electrical topology. Its model and improvement results are not VOLT-FORGE results.
- [SciPy maintainers' MAT-file format notes, issue 20192](https://github.com/scipy/scipy/issues/20192)
  explain the opaque MCOS/subsystem issue. The local decoder uses the installed,
  pinned SciPy MAT5 reader and a deliberately narrow schema inferred from these
  actual files; it is not a general MATLAB table library.

Only the ZIP and its embedded data files were acquired locally. The two papers
and dataset/licence pages were inspected through web retrieval; local PDF copies
or byte hashes for those web views are not claimed.

Normalized CSVs change current polarity to positive discharge and add source row
references. MATLAB table values are decoded without running MATLAB. Raw voltage,
time and surface-temperature values are preserved. Branch currents come from the
authors' processed measurements; their calibration is unresolved. Integrals,
linear calibration diagnostics, residuals, counts and plots are our derived
analysis. No synthetic data are used as observations, and no model predictions
appear in the measured-data figures.
