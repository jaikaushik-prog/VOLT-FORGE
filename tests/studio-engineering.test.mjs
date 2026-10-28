import test from 'node:test';
import assert from 'node:assert/strict';
import {conductorValues,conductorEditor} from '../web/editor/studio-conductors.mjs';
import {protectionResult} from '../web/editor/studio-protection.mjs';
import {pointValues,chartSvg} from '../web/editor/studio-charts.mjs';

const copper={length_mm:30,width_mm:8,thickness_mm:.2,contact_mohm:.2,resistivity_ohm_m:1.71e-8,density_kg_m3:8940,reference_temperature_C:20,material:'Copper',material_source:'https://copper.org/',assumption_source:'Declared dimensions'};

test('Dimension preview converts mm and SI material values to the hand-calculated mass and resistance',()=>{
 const v=conductorValues(copper);assert.ok(Math.abs(v.resistance_mohm-.520625)<1e-12);assert.ok(Math.abs(v.mass_g-.42912)<1e-12);
 const doubled=conductorValues({...copper,thickness_mm:.4});assert.ok(Math.abs(doubled.mass_g-.85824)<1e-12);assert.ok(doubled.resistance_mohm>v.resistance_mohm/2);
});

test('Physical source text cannot turn into an executable URL or injected markup',()=>{
 const html=conductorEditor({output:'negative',conductor:{...copper,material:'<img onerror=x>',material_source:'javascript:alert(1)'}},copper);
 assert.ok(html.includes('Remove this output route'));assert.ok(html.includes('&lt;img'));assert.ok(!html.includes('href="javascript:'));
});

test('A scheduled action beyond the computed horizon cannot be displayed as an actual disconnect',()=>{
 const experiment={graph:{cells:[{id:'c',name:'Cell <one>'}]},summary:{protection:{event:{cell:'c',detected_time_s:1,disconnect_time_s:5},actuated:false},service:{unserved_demand_s:0}}};
 assert.match(protectionResult(experiment),/outside the calculated horizon/);
 experiment.summary.protection.actuated=true;experiment.summary.service.unserved_demand_s=3;
 const html=protectionResult(experiment);assert.match(html,/3.00 s of requested demand was not served/);assert.match(html,/Cell &lt;one&gt;/);
});

test('Graph probes distinguish a physical cutoff from an ordinary load transition',()=>{
 const experiment={graph:{cells:[{name:'Cell 1'}]},rows:[{time_s:.5,event_side:'after',event_kind:'protective_disconnect',cell_current_A:[0]}]};
 assert.match(pointValues(experiment,'current',0),/after protection disconnect/);
});

test('A flat current series keeps distinct readable axis ticks',()=>{
 const experiment={graph:{cells:[{name:'Cell 1'}]},rows:[{time_s:0,cell_current_A:[4]},{time_s:60,cell_current_A:[4]}]};
 const labels=[...chartSvg(experiment,'current').matchAll(/text-anchor="end"[^>]*>([^<]+)<\/text>/g)].map(m=>m[1]);
 assert.equal(labels.length,5);assert.equal(new Set(labels).size,5);
});
