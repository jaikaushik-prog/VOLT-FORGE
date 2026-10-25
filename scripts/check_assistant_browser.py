"""Own-app browser acceptance for local commands; no external AI calls."""
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
    return {p.relative_to(folder).as_posix():file_hash(p) for p in folder.rglob('*') if p.is_file()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--chrome',type=Path,default=Path(os.environ.get('LOCALAPPDATA',''))/'Google/Chrome/Application/chrome.exe')
    args=parser.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    work=ROOT/'tmp'/('assistant_browser_'+uuid.uuid4().hex[:12]);work.mkdir()
    server=EditorServer(('127.0.0.1',0),work/'project');thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    browser=None;checks=[]
    try:
        b=browser=Browser(args.chrome,work/'profile',server.server_port)
        b.wait('document.querySelectorAll(".cell-group").length===4 && !document.querySelector("#run").disabled')
        b.js("window.requestURLs=[];window.realFetch=window.fetch;window.fetch=(...args)=>{requestURLs.push(String(args[0]));return realFetch(...args)}")
        assert b.js('document.querySelector("#assistant-panel").hidden')
        b.click('#assistant-toggle')
        assert 'No external AI calls' in b.js('document.querySelector("#assistant-panel").textContent')
        def command(message,ready):
            b.fill('#assistant-message',message);b.click('#assistant-send');b.wait(ready)
        command('help','document.querySelector("#assistant-response h3")?.textContent.includes("Supported local commands")')
        assert 'preview change selected rail' in b.js('document.querySelector("#assistant-response").textContent')
        command('explain this result','document.querySelector("#assistant-response h3")?.textContent.includes("Configuration")')
        assert 'No saved output selected' in b.js('document.querySelector("#assistant-response").innerText')
        b.screenshot(out/'01_configuration.png');checks.append('Initially closed, honestly labelled local command sheet; help and configuration-only evidence work.')
        b.click('#assistant-close');b.click('#run')
        b.wait('document.querySelector("#run-state").textContent.includes("Completed simulation / Current") && !document.querySelector("#run").disabled',seconds=90)
        first=b.js('document.querySelector("#run-select").value')
        b.click('#assistant-toggle');command('explain this result','document.querySelector("#assistant-response h3")?.textContent.includes("Current simulation evidence")')
        assert 'requirement not configured' in b.js('document.querySelector("#assistant-response").innerText')
        checks.append('Actual full A0 simulation is explained with saved values and no implied requirement pass.')
        # Delay genuine responses, then change selection while the reply is pending.
        b.js("window.savedFetch=window.fetch;window.fetch=async(...args)=>{const response=await savedFetch(...args);if(String(args[0]).includes('/api/assistant/request'))await new Promise(r=>setTimeout(r,600));return response}")
        b.fill('#assistant-message','explain this result');b.click('#assistant-send')
        b.click('#components [data-component=cell_2]')
        b.js('new Promise(resolve=>setTimeout(resolve,900))')
        assert b.js('document.querySelector("#assistant-response h3")===null')
        b.js('window.fetch=window.savedFetch')
        command('explain this result','document.querySelector("#assistant-response h3")?.textContent.includes("Current simulation evidence")')
        assert 'cell_2' in b.js('document.querySelector("#assistant-response").textContent')
        checks.append('A delayed response cannot overwrite a later component selection.')
        command('optimize the battery','document.querySelector("#assistant-response .error")?.textContent.includes("unsupported_command")')
        checks.append('Unsupported optimization is rejected without invented outcomes.')
        b.click('#assistant-close');b.click('#new-variant');b.fill('#variant-name','Command fixture');b.click('#variant-form button[type=submit]')
        b.wait('document.querySelector("#variant-title").textContent.startsWith("A1") && !document.querySelector("#run").disabled')
        b.click('#components [data-component=rail_p_1]');b.click('#assistant-toggle')
        before=tree(work/'project')
        command('preview change positive rail 1 to 0.5 mOhm','document.querySelector("#assistant-review")!==null')
        assert tree(work/'project')==before
        # Changing/reverting the command during review cancels the late draft.
        b.js("window.beforeReviewFetch=window.fetch;window.fetch=async(...args)=>{const response=await beforeReviewFetch(...args);if(String(args[0]).includes('/api/evidence/request'))await new Promise(r=>setTimeout(r,600));return response}")
        b.click('#assistant-review');b.fill('#assistant-message','help');b.fill('#assistant-message','preview change positive rail 1 to 0.5 mOhm')
        b.wait('!document.querySelector("#run").disabled');b.js('new Promise(resolve=>setTimeout(resolve,800))')
        assert b.js('document.querySelector("#apply-edit").disabled')
        assert not b.js('document.querySelector("#assistant-panel").hidden')
        assert tree(work/'project')==before
        b.js('window.fetch=window.beforeReviewFetch')
        checks.append('Changing and reverting a command during inspector revalidation cancels the late preview handoff.')
        command('preview change positive rail 1 to 0.5 mOhm','document.querySelector("#assistant-review")!==null')
        b.screenshot(out/'02_command_preview.png')
        b.click('#assistant-review')
        b.wait('document.querySelector("#assistant-panel").hidden && !document.querySelector("#apply-edit").disabled')
        assert tree(work/'project')==before
        assert b.js('document.querySelector("#edit-value").value')=='0.5'
        b.click('#apply-edit');b.wait('document.querySelector("#notice").textContent.startsWith("Revision saved") && !document.querySelector("#run").disabled')
        project=Project(work/'project');info=project.inspect('A1')
        assert info['design']['connections']['rail_p_1']['resistance']['value']==.0005
        assert all(r['owner_variant_id']!='A1' for r in info['runs'])
        checks.append('Command and inspector review preserve all project bytes; separate manual Apply changes only the declared input and starts no run.')
        b.click('#run');b.wait('document.querySelector("#run-state").textContent.includes("Completed simulation / Current") && !document.querySelector("#run").disabled',seconds=90)
        second=b.js('document.querySelector("#run-select").value')
        b.click('#tab-compare');b.fill('#compare-first',first,True);b.fill('#compare-second',second,True)
        b.click('#assistant-toggle');before=tree(work/'project')
        command('compare selected runs','document.querySelector("#assistant-response h3")?.textContent==="Simulation comparison"')
        assert tree(work/'project')==before
        assert 'identical operating conditions' in b.js('document.querySelector("#assistant-response").innerText')
        for width,height,name in [(1440,1000,'03_compare_desktop'),(1920,1080,'04_compare_wide'),(1024,900,'05_compare_tablet'),(390,844,'06_compare_phone')]:
            b.call('Emulation.setDeviceMetricsOverride',dict(width=width,height=height,deviceScaleFactor=1,mobile=width<500))
            b.wait(f'window.innerWidth==={width}')
            assert b.js('document.documentElement.scrollWidth<=window.innerWidth'),name
            assert b.js('document.querySelector(".command-table").scrollWidth<=document.querySelector(".command-table").clientWidth'),name
            b.screenshot(out/(name+'.png'))
        b.call('Emulation.setDeviceMetricsOverride',dict(width=1440,height=1000,deviceScaleFactor=1,mobile=False))
        checks.append('Read-only comparison preserves explicit A0/A1 identities, backend deltas and limitations; four viewport widths have no document overflow.')
        b.fill('#compare-second',first,True)
        assert b.js('document.querySelector("#assistant-response h3")===null')
        checks.append('Changing comparison selections invalidates the previous comparison response.')
        b.click('#assistant-close');b.click('#components [data-component=rail_p_1]');b.click('#assistant-toggle')
        command('preview change selected rail to 0.4 mOhm','document.querySelector("#assistant-review")!==null')
        project=Project(work/'project');info=project.inspect('A1')
        project.apply_edit('A1',dict(target='connection',id='rail_n_1',property='resistance',value=.0006,unit='ohm',classification='assumed',source='Synthetic concurrent-edit fixture'),info['revision_id'])
        after=tree(work/'project');b.click('#assistant-review')
        b.wait('document.querySelector("#assistant-response .error")?.textContent.includes("stale_context")')
        assert tree(work/'project')==after
        checks.append('An external design revision rejects inspector review of a stale command without further writes.')
        assert b.js('window.requestURLs.every(path=>path.startsWith("/api/"))')
        expected=[x for x in b.errors if x.get('source')=='network' and any(str(code) in x.get('text','') for code in [400,409])]
        unexpected=[x for x in b.errors if x not in expected];assert not unexpected,unexpected
        receipt=dict(status='passed',checks=checks,browser_errors=unexpected,expected_rejections=len(expected),
            external_ai_calls=0,scope='Software checks on reference project; synthetic concurrent-edit fixture; no new measured outcomes',
            screenshots={p.name:file_hash(p) for p in out.glob('*.png')})
        (out/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt,indent=2))
    except Exception as exc:
        (out/'attempt.json').write_text(json.dumps(dict(status='failed',error=str(exc),checks=checks),indent=2),encoding='utf-8')
        if browser:browser.screenshot(out/'failure.png')
        raise
    finally:
        if browser:browser.close()
        server.shutdown();server.server_close();thread.join(timeout=5)


if __name__=='__main__':main()
