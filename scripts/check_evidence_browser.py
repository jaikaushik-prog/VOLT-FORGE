"""Real local-editor acceptance checks, with synthetic setup and saved screenshots."""
import argparse
import json
import os
from pathlib import Path
import threading
import uuid

from check_editor_browser import Browser
from run_editor import EditorServer, ROOT
from voltforge.project import Project
from voltforge.project.service import file_hash


def tree(folder):
    return {p.relative_to(folder).as_posix(): file_hash(p) for p in folder.rglob('*') if p.is_file()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chrome',type=Path,default=Path(os.environ.get('LOCALAPPDATA',''))/'Google/Chrome/Application/chrome.exe')
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    work=ROOT/'tmp'/('evidence_browser_'+uuid.uuid4().hex[:12]);work.mkdir()
    server=EditorServer(('127.0.0.1',0),work/'project')
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    browser=None;observations=[]
    try:
        b=browser=Browser(args.chrome,work/'profile',server.server_port)
        b.wait('document.querySelectorAll(".cell-group").length===4 && !document.querySelector("#run").disabled')
        b.click('#tab-evidence')
        b.wait('document.querySelector(".evidence-status")?.textContent.includes("Configuration evidence")')
        assert 'No saved result selected' in b.js('document.querySelector("#panel-evidence").innerText')
        assert b.js('document.querySelectorAll(".evidence-source").length')>0
        b.screenshot(out/'01_configuration.png')
        observations.append('Configuration-only evidence has fitted/assumed inputs, expandable citations and no saved output.')
        b.click('#run')
        b.wait('document.querySelector("#run-state").textContent.includes("Completed simulation / Current") && !document.querySelector("#run").disabled',seconds=80)
        b.wait('document.querySelector(".evidence-status")?.textContent.includes("Current simulation evidence")')
        rid=b.js('document.querySelector("#run-select").value')
        assert 'requirement not configured' in b.js('document.querySelector("#panel-evidence").innerText')
        assert 'Experimental module validation pending' in b.js('document.querySelector("#panel-evidence").innerText')
        observations.append('Actual full A0 run displays current evidence and requirement-not-configured without acceptance.')
        b.click('#components [data-component=cell_2]')
        b.wait('document.querySelector(".evidence-heading p")?.textContent.includes("cell 2") && document.querySelector(".evidence-status")?.textContent.includes("Current simulation evidence")')
        b.js('document.querySelectorAll(".evidence-group").forEach(e=>{if(e.textContent.includes("Configured assumptions"))e.open=true})')
        assert 'P17' in b.js('document.querySelector("#panel-evidence").textContent')
        b.js('document.querySelector(".evidence-source").open=true')
        for width,height,name in [(1440,1000,'02_evidence_desktop'),(1920,1080,'03_evidence_wide'),(1024,900,'04_evidence_tablet'),(390,844,'05_evidence_phone')]:
            b.call('Emulation.setDeviceMetricsOverride',dict(width=width,height=height,deviceScaleFactor=1,mobile=width<500))
            b.wait(f'window.innerWidth==={width}')
            b.js('document.querySelector("#panel-evidence").scrollIntoView({block:"start"})')
            assert b.js('document.documentElement.scrollWidth<=window.innerWidth'),name
            b.screenshot(out/(name+'.png'))
        b.call('Emulation.setDeviceMetricsOverride',dict(width=1440,height=1000,deviceScaleFactor=1,mobile=False))
        observations.append('Selected P17 evidence and source details render without document overflow at1440,1920,1024,390px.')
        # Delay genuine server responses; do not replace any returned physics.
        b.js("window.originalFetch=window.fetch;window.fetch=async(...args)=>{const response=await originalFetch(...args);if(String(args[0]).includes('/api/evidence/request'))await new Promise(r=>setTimeout(r,250));return response}")
        b.click('#components [data-component=cell_1]');b.click('#components [data-component=cell_3]')
        b.wait('document.querySelector(".evidence-heading p")?.textContent.includes("cell 3") && document.querySelector(".evidence-status")?.textContent.includes("Current simulation evidence")')
        assert 'P19' in b.js('document.querySelector("#panel-evidence").textContent')
        b.js('window.fetch=window.originalFetch')
        observations.append('Delayed genuine evidence responses cannot overwrite a later component selection.')
        # Keyboard display moves must update selection without changing physics.
        old_revision=Project(work/'project').inspect('A0')['revision_id']
        b.js('document.querySelector(".cell-group[data-component=cell_4]").dispatchEvent(new KeyboardEvent("keydown",{key:"ArrowLeft",bubbles:true}))')
        b.wait('document.querySelector(".evidence-heading p")?.textContent.includes("cell 4") && document.querySelector(".evidence-status")?.textContent.includes("Current simulation evidence") && !document.querySelector("#run").disabled')
        assert Project(work/'project').inspect('A0')['revision_id']==old_revision
        assert 'P13' in b.js('document.querySelector("#inspector-content").textContent')
        observations.append('Keyboard layout changes update component evidence while preserving the physics revision and current run.')

        b.click('#components [data-component=rail_p_1]')
        b.wait('document.querySelector(".evidence-status")?.textContent.includes("Current simulation evidence")')
        before=tree(work/'project')
        b.fill('#edit-value','0.5');b.click('#preview-edit')
        b.wait('!document.querySelector("#apply-edit").disabled')
        assert tree(work/'project')==before
        assert 'effect on current or voltage has not been calculated' in b.js('document.querySelector("#edit-feedback").innerText')
        b.js('document.querySelector("#edit-feedback").scrollIntoView({block:"start"})');b.screenshot(out/'06_review_preview.png')
        b.fill('#edit-value','0.6');assert b.js('document.querySelector("#apply-edit").disabled')
        b.fill('#edit-value','0.5');assert b.js('document.querySelector("#apply-edit").disabled')
        observations.append('Preview preserves every project byte; changing and reverting the input still requires a new preview.')
        b.click('#preview-edit');b.wait('!document.querySelector("#apply-edit").disabled')
        # An external declared edit makes the captured preview stale; manual
        # Apply must revalidate before invoking the existing mutation operation.
        project=Project(work/'project');info=project.inspect('A0')
        external=dict(target='connection',id='rail_n_1',property='resistance',value=.0006,unit='ohm',classification='assumed',source='Synthetic concurrent-edit software fixture')
        project.apply_edit('A0',external,info['revision_id']);after_external=tree(work/'project')
        b.click('#apply-edit');b.wait('document.querySelector("#notice").textContent.includes("stale_context")')
        assert tree(work/'project')==after_external
        assert b.js('document.querySelector("#apply-edit").disabled')
        observations.append('An external revision invalidates preview; manual Apply rechecks and leaves the project unchanged.')
        b.call('Page.reload',{})
        b.wait('document.querySelectorAll(".cell-group").length===4 && !document.querySelector("#run").disabled')
        b.fill('#run-select',rid,True);b.wait('document.querySelector("#run-state").textContent.includes("Outdated for this design")')
        b.click('#tab-evidence');b.wait('document.querySelector(".evidence-status")?.textContent.includes("Historical simulation evidence")')
        assert 'Outdated:' in b.js('document.querySelector("#panel-evidence").innerText')
        b.screenshot(out/'07_historical_evidence.png')
        b.click('#new-variant');b.fill('#variant-name','Evidence preview fixture');b.click('#variant-form button[type=submit]')
        b.wait('document.querySelector("#variant-title").textContent.startsWith("A1") && !document.querySelector("#run").disabled')
        b.fill('#run-select',rid,True);b.wait('document.querySelector("#run-state").textContent.includes("Outdated for this design")')
        b.wait('document.querySelector(".evidence-status")?.textContent.includes("Historical simulation evidence")')
        b.click('#components [data-component=rail_p_1]');b.fill('#edit-value','0.5');b.click('#preview-edit')
        b.wait('!document.querySelector("#apply-edit").disabled')
        old_runs=len(Project(work/'project').inspect('A1')['runs'])
        b.click('#apply-edit');b.wait('document.querySelector("#notice").textContent.startsWith("Revision saved") && !document.querySelector("#run").disabled')
        assert Project(work/'project').inspect('A1')['design']['connections']['rail_p_1']['resistance']['value']==.0005
        assert len(Project(work/'project').inspect('A1')['runs'])==old_runs
        observations.append('Explicit manual Apply creates the declared A1 revision, preserves historical ownership and never starts a simulation.')
        # Deliberately unsupported load exercises domain-stop presentation.
        b.click('#components [data-component=module]')
        b.fill('#edit-json',json.dumps([dict(start_s=0,end_s=2,current_A=100000)]));b.click('#preview-edit')
        b.wait('!document.querySelector("#apply-edit").disabled');b.click('#apply-edit')
        b.wait('document.querySelector("#notice").textContent.startsWith("Revision saved") && !document.querySelector("#run").disabled')
        b.click('#run');b.wait('document.querySelector("#run-state").textContent.includes("Failed simulation") && !document.querySelector("#run").disabled')
        b.wait('document.querySelector(".evidence-status")?.textContent.includes("Failed run")')
        assert b.js('document.querySelector(".evidence-failure")?.textContent.length')>0
        b.screenshot(out/'08_failed_evidence.png')
        observations.append('Failed partial simulation retains its exact stop reason, partial status and evidence limitations.')
        # Plain untrusted source text is never markup, even inside citations.
        b.fill('#edit-property','step',True);b.fill('#edit-source','<img src=x onerror="window.injected=true">');b.fill('#edit-value','0.2');b.click('#preview-edit')
        b.wait('!document.querySelector("#apply-edit").disabled')
        assert 'Seconds are defined by the supported project schema' in b.js('document.querySelector("#edit-feedback").textContent')
        assert b.js('document.querySelectorAll("#edit-feedback img").length')==0
        assert not b.js('Boolean(window.injected)')
        observations.append('Untrusted provenance is escaped as text in previews; no injected markup or script executes.')
        expected=[x for x in b.errors if x.get('source')=='network' and '409' in x.get('text','')]
        errors=[x for x in b.errors if x not in expected]
        assert not errors,errors
        receipt=dict(status='passed',observations=observations,browser_errors=errors,expected_conflict_responses=len(expected),
            project=str((work/'project').relative_to(ROOT)),scope='Software integration only; synthetic fault/setup edits; no new experimental outcomes',
            screenshots={p.name:file_hash(p) for p in out.glob('*.png')})
        (out/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(receipt,indent=2))
    except Exception as exc:
        (out/'attempt.json').write_text(json.dumps(dict(status='failed',error=str(exc),observations=observations),indent=2),encoding='utf-8')
        if browser:
            browser.screenshot(out/'failure.png')
        raise
    finally:
        if browser:browser.close()
        server.shutdown();server.server_close();thread.join(timeout=5)


if __name__=='__main__':main()
