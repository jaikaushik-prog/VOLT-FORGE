import test from 'node:test';
import assert from 'node:assert/strict';
import {Walkthrough,TOUR_VERSION} from '../web/editor/studio-walkthrough.mjs';
import {chartSvg,nearestIndex,pointValues} from '../web/editor/studio-charts.mjs';

test('Guide cannot treat the wrong design, an unprobed test or an unrelated comparison as complete',()=>{
 const data=new Map(),storage={getItem:k=>data.get(k),setItem:(k,v)=>data.set(k,v)},tour=new Walkthrough(storage);
 tour.start('example','my_work');assert.equal(tour.complete({designId:'other',rendered:true}),false);
 assert.equal(tour.next({designId:'example',rendered:true}),true);
 assert.equal(tour.next({designId:'example',selectedCell:true,inspector:false}),false);
 assert.equal(tour.next({designId:'example',selectedCell:true,inspector:true}),true);
 tour.mark('reviewed');tour.next({designId:'example'});tour.mark('baselineId','first_test');
 assert.equal(tour.next({}),false);tour.mark('probed');assert.equal(tour.next({}),true);
 tour.mark('alternativeId','second_test');
 assert.equal(tour.next({comparedIds:['unrelated','second_test'],sameConditions:true}),false);
 assert.equal(tour.next({comparedIds:['first_test','second_test'],sameConditions:false}),false);
 assert.equal(tour.next({comparedIds:['first_test','second_test'],sameConditions:true}),true);
 assert.equal(tour.next({}),false);assert.equal(tour.next({},true),true);
 const reopened=new Walkthrough(storage);assert.equal(reopened.state.step,6);assert.equal(reopened.state.returnId,'my_work');
 reopened.dismiss();assert.equal(new Walkthrough(storage).state.active,false);
 assert.equal(JSON.parse(data.get(TOUR_VERSION)).seen,true);
});

test('Denied browser storage does not prevent using or skipping the guide',()=>{
 const tour=new Walkthrough({getItem(){throw Error('denied');},setItem(){throw Error('denied');}});
 tour.start('example',null);tour.dismiss();assert.equal(tour.state.active,false);
});

test('Chart distinguishes both sides of an actual current event and defaults to after',()=>{
 const experiment={graph:{cells:[{name:'Cell 1'}]},rows:[
 {time_s:0,cell_current_A:[1]},
 {time_s:10,event_side:'before',cell_current_A:[1]},
 {time_s:10,event_side:'after',cell_current_A:[3]},
 {time_s:11,cell_current_A:[3]}]};
 assert.equal(nearestIndex(experiment.rows,10),2);
 assert.match(pointValues(experiment,'current',1),/before load change/);
 assert.match(pointValues(experiment,'current',2),/after load change/);
 assert.match(pointValues(experiment,'current',2),/3.00/);
});

test('Missing thermal evidence renders an unavailable state instead of a zero-degree graph',()=>{
 const experiment={graph:{cells:[{name:'My cell'}]},rows:[{time_s:0,temperature_C:[null]},{time_s:10,temperature_C:[null]}]};
 const html=chartSvg(experiment,'temperature');assert.match(html,/Temperature is not modeled/);assert.doesNotMatch(html,/<polyline/);
 assert.match(pointValues(experiment,'temperature',1),/Not modeled/);
});
