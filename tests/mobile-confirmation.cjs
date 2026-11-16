// 不依赖微信运行时，验证服务拒绝/断网不会在本地伪造处置成功。
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const source = path.join(__dirname, '../src/护工移动端/services/care-service.js')
let online = true
let fail = true
let saves = 0
const api = {
  isServiceAvailable: () => online,
  updateEvent: async (id, payload) => {
    assert.equal(payload.handled_by, 'caregiver-test')
    if (fail) throw new Error('尚未到场')
    return { event_id: id, status: '已处理', position: '模拟走廊' }
  }
}
const store = {
  getCaregiverProfile: () => ({ id: 'caregiver-test' }),
  upsertCenterAlert: item => { saves++; return item }
}
const sandbox = { module: { exports: {} }, require: name => name.includes('/api') ? api : store }
vm.runInNewContext(fs.readFileSync(source, 'utf8'), sandbox)
;(async () => {
  const update = sandbox.module.exports.updateCenterAlertStatus
  await assert.rejects(update('e1', '已完成'), /尚未到场/)
  assert.equal(saves, 0)
  online = false
  await assert.rejects(update('e1', '已完成'), /离线/)
  assert.equal(saves, 0)
  online = true
  fail = false
  const item = await update('e1', '已完成')
  assert.equal(item.status, '已完成')
  assert.equal(item.location, '模拟走廊')
  assert.equal(saves, 1)
  console.log('移动端确认一致性测试通过')
})().catch(error => { console.error(error); process.exitCode = 1 })
