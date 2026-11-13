import test from 'node:test'
import assert from 'node:assert/strict'
import {cents, measurement, candidateInput, evaluationInput, newLaptop, initialRecords} from '../src/model.ts'

const requirements = {ram:'16', storage:'512', ceiling:'900', noLimit:false, compatibility:true}
const plan = {savings:'300', contribution:'150', firstDate:'2027-01-31', targetDate:'2027-03-31', essential:false,
  useBudget:false, income:'1600', housing:'700', food:'250', transportation:'180', other:'120', goals:'150', buffer:'50',
  useScenario:false, category:'transportation', reduction:'40', allocation:'40'}

test('money converts decimal strings into exact cents', () => {
  assert.equal(cents('0.29','Amount'),29)
  assert.equal(cents('16.67','Amount'),1667)
  assert.equal(cents(' 150.5 ','Amount'),15050)
  assert.equal(cents('0','Amount'),0)
})
test('unknown amounts stay unknown; required amounts cannot be blank', () => {
  assert.equal(cents('','Amount',true),null)
  for (const value of ['', '-1', '1.001', 'Infinity', '1e3', '10000000001'])
    assert.throws(() => cents(value,'Amount'))
})
test('unknown measurements and invalid values are distinct', () => {
  assert.equal(measurement('','RAM'),null)
  assert.equal(measurement('16','RAM'),16)
  for (const value of ['0','-1','1.5','NaN']) assert.throws(() => measurement(value,'RAM'))
})
test('a partial configuration can be reviewed without inventing specs or tax', () => {
  const draft = {...newLaptop('a'), name:'A', configuration:'Specific build'}
  const input = candidateInput(draft)
  assert.equal(input.confirmed,true)
  assert.equal(input.ram_gb,null)
  assert.equal(input.cost.tax_cents,null)
  assert.equal(input.compatible,'unknown')
})
test('product identity and source link are validated before confirmation', () => {
  assert.throws(() => candidateInput(newLaptop('a')))
  const draft = {...newLaptop('a'), name:'A', configuration:'Build', source:'javascript:alert(1)'}
  assert.throws(() => candidateInput(draft))
  assert.doesNotThrow(() => candidateInput({...draft,source:'https://example.com/laptop'}))
})
test('only the last confirmed revision reaches the API', () => {
  const records = initialRecords()
  records[1].confirmed = {...records[1].draft}
  records[1].draft.ram = '32'
  const input = evaluationInput(records,requirements,plan,{})
  assert.equal(input.candidates.length,1)
  assert.equal(input.candidates[0].ram_gb,16)
})
test('removing the price limit preserves technical requirements', () => {
  const input = evaluationInput([], {...requirements,noLimit:true}, plan,{})
  assert.equal(input.requirements.max_cost_cents,null)
  assert.equal(input.requirements.min_ram_gb,16)
  assert.equal(input.requirements.require_compatibility,true)
})
test('scenario is separate from the unchanged base contribution and budget', () => {
  const input = evaluationInput([],requirements,{...plan,useBudget:true,useScenario:true},{})
  assert.equal(input.plan.contribution_cents,15000)
  assert.equal(input.plan.budget.expenses.transportation,18000)
  assert.equal(input.plan.scenario.allocation_cents,4000)
})
