"""Declared initial-state uncertainty stress case; synthetic software evidence."""
from voltforge.models import improvement as m
from voltforge.models.coupling import simulate


def main():
    m.check_procedure();selected=m.read_json(m.OUT/'selection.json')['selected']
    cells=['P7','P17','P19','P13'];models=[m.read_json(m.OUT/'development'/f'{c}_models.json')[selected] for c in cells]
    initial=[.72,.70,.68,.70];f=simulate(models,initial,14.55,360.,.25,.001)
    out=m.OUT/'software_coupling';f.to_csv(out/'SOC_imbalance_synthetic.csv',index=False)
    result=dict(status='Synthetic software stress check, not experimental evidence',cell_order=cells,
        assumed_initial_soc=initial,module_A=14.55,duration_s=360,rail_segment_ohm=.001,
        branch_ranges_A={c:[float(f[f'I{k+1}_A'].min()),float(f[f'I{k+1}_A'].max())] for k,c in enumerate(cells)},
        max_kcl_residual_A=float(abs(f.kcl_residual_A).max()),max_charge_balance_As=float(abs(f.total_charge_balance_As).max()),
        interpretation='Small initial SOC imbalance can place a branch above the 4.85 A six-minute characterization plateau. Short higher-current multisines do not establish accuracy for this dwell.')
    m.save(out/'initial_soc_imbalance.json',result)
    print(result)


if __name__=='__main__': main()
