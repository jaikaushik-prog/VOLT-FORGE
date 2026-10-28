export const TOUR_VERSION='voltforge.walkthrough/1';
export const tourSteps=[
 {id:'open_example',title:'Start with an example',body:'Four cells are connected to share the load. This example is separate from your own designs.'},
 {id:'inspect_cell',title:'Get to know a cell',body:'Select a cell on the canvas. Its starting charge tells you how full it is; its starting temperature tells you how warm it is.'},
 {id:'review_test',title:'Choose the test',body:'Open Test and review the load, duration and room temperature. These are the conditions the solver will use.'},
 {id:'run_and_probe',title:'See what happens',body:'Run the test, then point at the chart or move its time slider. You are inspecting values from the saved calculation.'},
 {id:'compare_one_change',title:'Compare one change',body:'Move the negative output to the other end of the battery. Preview the change, then test a copy under the same conditions.'},
 {id:'ask_copilot',title:'Ask why it changed',body:'Ask the copilot about the two saved tests. It receives their results and assumptions. You choose when to send the question.'},
 {id:'export_or_create',title:'Try your own idea',body:'Export the experiment, start your own design or add a custom cell. Your example and its results stay saved.'}
];
export const comparisonQuestion='What changed between these two tests, and which assumptions matter for the comparison?';
export class Walkthrough {
 constructor(storage){this.storage=storage;this.state={version:TOUR_VERSION,seen:false,active:false,step:0};try{const value=JSON.parse(storage.getItem(TOUR_VERSION));if(value?.version===TOUR_VERSION&&Number.isInteger(value.step)&&value.step>=0&&value.step<tourSteps.length)this.state={...this.state,...value};}catch{}}
 save(){try{this.storage.setItem(TOUR_VERSION,JSON.stringify(this.state));}catch{}}
 start(exampleId,returnId){this.state={version:TOUR_VERSION,seen:true,active:true,step:0,exampleId,returnId,baselineId:null,alternativeId:null,reviewed:false,probed:false,aiAnswered:false};this.save();}
 dismiss(){this.state.seen=true;this.state.active=false;this.save();}
 mark(key,value=true){this.state[key]=value;this.save();}
 back(){this.state.step=Math.max(0,this.state.step-1);this.save();}
 next(context,skip=false){if(!skip&&!this.complete(context))return false;if(this.state.step===tourSteps.length-1)this.dismiss();else{this.state.step++;this.save();}return true;}
 complete(c){const t=this.state;if(!t.active)return false;switch(t.step){
 case 0:return c.designId===t.exampleId&&c.rendered;
 case 1:return c.designId===t.exampleId&&c.selectedCell&&c.inspector;
 case 2:return c.designId===t.exampleId&&t.reviewed;
 case 3:return !!t.baselineId&&t.probed;
 case 4:return !!t.baselineId&&!!t.alternativeId&&c.comparedIds?.includes(t.baselineId)&&c.comparedIds?.includes(t.alternativeId)&&c.sameConditions;
 case 5:return !!t.aiAnswered;
 case 6:return !!t.exported;
 default:return false;
 }}
}
