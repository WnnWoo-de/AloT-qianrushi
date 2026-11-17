const api = require('../utils/api')
const store = require('../utils/store')

function local(value) {
  return Promise.resolve(value)
}

function withFallback(remoteCall, localCall, save) {
  if (!api.isServiceAvailable()) return local(localCall())
  return remoteCall()
    .then(function (value) {
      const next = save ? save(value) : value
      return next === undefined ? value : next
    })
    .catch(function () {
      return localCall()
    })
}

function eventPayload(event, source) {
  const suffix = Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8)
  const position = event.position || event.location || event.area || '未提供位置'
  return Object.assign({}, event, {
    event_id: event.event_id || event.id || (source + '-' + suffix),
    run_id: event.run_id || (source + '-run-' + suffix),
    type: event.type || event.event_type || event.alertType || '护工上报',
    position: typeof position === 'string' ? position : (position.name || '未提供位置'),
    source: event.source || source,
    timestamp: event.timestamp || event.created_at || event.createdAt
  })
}

function normalizeEvent(event) {
  const payload = Object.assign({}, event.payload || event.data || {}, event)
  return Object.assign({}, payload, {
    id: payload.id || payload.event_id,
    alertType: payload.alertType || payload.alert_type || payload.type || payload.event_type,
    level: payload.level || payload.severity || '',
    status: payload.status === '已处理' || payload.status === '已完成' ? '已完成' : (payload.status === '失败' ? '失败' : (payload.care_started_at || payload.status === '处理中' ? '处理中' : '待响应')),
    location: payload.location || (typeof payload.position === 'string' ? payload.position : (payload.position && payload.position.name)) || payload.area || '',
    createdAt: payload.createdAt || payload.created_at || payload.timestamp || '',
    popupShown: payload.popupShown !== undefined ? payload.popupShown : Boolean(payload.popup_shown)
  })
}

function taskPayload(task) {
  return Object.assign({}, task, {
    task_id: task.task_id || task.id,
    title: task.title || task.content,
    timestamp: task.timestamp || task.created_at || task.createdAt
  })
}

function normalizeTask(task) {
  const payload = Object.assign({}, task.payload || task.data || {}, task)
  return Object.assign({}, payload, {
    id: payload.id || payload.task_id,
    content: payload.content || payload.title || payload.task || '',
    priority: payload.priority || '中',
    done: payload.done !== undefined ? Boolean(payload.done) : payload.status === '已完成',
    createdAt: payload.createdAt || payload.created_at || payload.timestamp || ''
  })
}

function getElders() {
  return withFallback(
    function () { return api.getElders() },
    function () { return store.getElders() },
    function (list) { return store.replaceElders(Array.isArray(list) ? list : []) }
  )
}

function getElderById(elderId) {
  return withFallback(
    function () { return api.getElder(elderId) },
    function () { return store.getElderById(elderId) },
    function (elder) {
      if (!elder) return store.getElderById(elderId)
      const elders = store.getElders().slice()
      const index = elders.findIndex(function (item) { return item.id === elder.id })
      if (index >= 0) elders[index] = elder
      else elders.push(elder)
      store.replaceElders(elders)
      return elder
    }
  )
}

function getLogs(params) {
  return withFallback(
    function () { return api.getCareLogs(params && params.elderId ? { elderId: params.elderId } : {}) },
    function () {
      let logs = store.getLogs()
      if (params && params.elderId) logs = logs.filter(function (item) { return item.elderId === params.elderId })
      return logs
    },
    function (list) {
      const logs = Array.isArray(list) ? list : []
      if (!(params && params.elderId)) store.replaceLogs(logs)
      return logs
    }
  )
}

function addLog(payload) {
  if (!api.isServiceAvailable()) return local(store.addLog(payload))
  return api.createCareLog(payload)
    .then(function (item) { return store.addLog(item || payload) })
    .catch(function () { return store.addLog(payload) })
}

function getManualAlerts() {
  return withFallback(
    function () { return api.getEvents({ source: 'caregiver' }) },
    function () { return store.getAlerts() },
    function (list) { return store.replaceAlerts((Array.isArray(list) ? list : []).map(normalizeEvent)) }
  )
}

function addManualAlert(payload) {
  // 报警中心必须收到真实回执；断网或失败时不能只在本地伪造“已上报”。
  if (!api.isServiceAvailable()) return Promise.reject(new Error('服务离线，报警尚未提交'))
  return api.createEvent(eventPayload(payload, 'caregiver'))
    .then(function (item) { return store.addAlert(normalizeEvent(item)) })
}

function getTodos() {
  return withFallback(
    function () { return api.getTasks({ client: 'caregiver' }) },
    function () { return store.getTodos() },
    function (list) { return store.replaceTodos((Array.isArray(list) ? list : []).map(normalizeTask)) }
  )
}

function addTodo(payload) {
  if (!api.isServiceAvailable()) return local(store.addTodo(payload))
  return api.createTask(taskPayload(payload))
    .then(function (item) {
      const todo = normalizeTask(item || payload)
      if (!todo.id) return store.addTodo(payload)
      store.upsertTodo(todo)
      return todo
    })
    .catch(function () { return store.addTodo(payload) })
}

function toggleTodoDone(todoId, done) {
  if (!api.isServiceAvailable()) return local(store.toggleTodoDone(todoId))
  return api.updateTask(todoId, { done, status: done ? '已完成' : '待处理' })
    .then(function (item) {
      if (item) store.upsertTodo(normalizeTask(item))
      else store.toggleTodoDone(todoId)
      return store.getTodos()
    })
    .catch(function () { return store.toggleTodoDone(todoId) })
}

function deleteTodo(todoId) {
  if (!api.isServiceAvailable()) return local(store.deleteTodo(todoId))
  return api.deleteTask(todoId)
    .then(function () { return store.deleteTodo(todoId) })
    .catch(function () { return store.deleteTodo(todoId) })
}

function getCenterAlerts(params) {
  return withFallback(
    function () { return api.getEvents({ source: 'center' }) },
    function () { return params && params.pendingOnly ? store.getPendingCenterAlerts() : store.getCenterAlerts() },
    function (list) {
      const alerts = store.replaceCenterAlerts((Array.isArray(list) ? list : []).map(normalizeEvent))
      return params && params.pendingOnly ? alerts.filter(function (item) { return item.status !== '已完成' }) : alerts
    }
  )
}

function getCenterAlertById(alertId) {
  return withFallback(
    function () { return api.getEvent(alertId) },
    function () { return store.getCenterAlertById(alertId) },
    function (item) {
      if (!item) return store.getCenterAlertById(alertId)
      return store.upsertCenterAlert(normalizeEvent(item))
    }
  )
}

function getNextPopupCenterAlert() {
  return getCenterAlerts().then(function () { return store.getNextPopupCenterAlert() })
}

function markCenterAlertPopupShown(alertId) {
  const localUpdate = function () { return store.markCenterAlertPopupShown(alertId) }
  if (!api.isServiceAvailable()) return local(localUpdate())
  return api.updateEvent(alertId, { popup_shown: true })
    .then(function () { return localUpdate() })
    .catch(function () { return localUpdate() })
}

function updateCenterAlertStatus(alertId, status) {
  // 护工确认必须得到服务端成功回执，不能断网后只改缓存并显示成功。
  if (!api.isServiceAvailable()) return Promise.reject(new Error('服务离线，尚未完成云端确认，请恢复网络后重试'))
  const profile = store.getCaregiverProfile()
  const handledBy = profile.id || profile.caregiver_id || profile.name
  if (!handledBy) return Promise.reject(new Error('请先配置护工身份'))
  return api.updateEvent(alertId, { status, handled_by: handledBy })
    .then(function (item) { return store.upsertCenterAlert(normalizeEvent(item)) })
}

function getCaregiverProfile() {
  return withFallback(
    function () { return api.getCaregiverProfile() },
    function () { return store.getCaregiverProfile() },
    function (profile) { return store.setCaregiverProfile(profile) }
  )
}

function getDashboardStats() {
  return withFallback(
    function () { return api.getStatistics() },
    function () { return store.getCachedStatistics() || store.getDashboardStats() },
    function (statistics) {
      const value = statistics && statistics.caregiver ? statistics.caregiver : statistics
      if (!value || typeof value !== 'object') return store.getDashboardStats()
      return store.setCachedStatistics(value)
    }
  )
}

function refreshCoreState() {
  if (!api.isServiceAvailable()) return Promise.resolve()
  return Promise.allSettled([
    api.getSystemStatus().then(function (value) { store.setServiceCache('system', value) }),
    getElders(),
    getLogs(),
    getManualAlerts(),
    getCenterAlerts(),
    getTodos(),
    getDashboardStats(),
    getCaregiverProfile()
  ])
}

function handleRealtimeMessage(message) {
  if (!message || !message.type) return
  if (message.type === 'event_update') {
    const items = Array.isArray(message.data) ? message.data : [message.data]
    items.filter(Boolean).forEach(function (item) { store.upsertCenterAlert(normalizeEvent(item)) })
  } else if (message.type === 'task_update') {
    const items = Array.isArray(message.data) ? message.data : [message.data]
    // 协同派单任务带 event_id/robot_id，只更新报警详情，不能污染护工个人待办。
    items.filter(function (item) { return item && !item.event_id && !item.robot_id })
      .forEach(function (item) { store.upsertTodo(normalizeTask(item)) })
  } else if (message.type === 'system_update') {
    store.setServiceCache('system', message.data)
  } else if (message.type === 'robot_update') {
    store.setServiceCache('robots', message.data)
  }
}

function probeService(force) {
  return api.probeService(force)
}

function isServiceAvailable() {
  return api.isServiceAvailable()
}

module.exports = {
  probeService,
  isServiceAvailable,
  getElders,
  getElderById,
  getLogs,
  addLog,
  getManualAlerts,
  addManualAlert,
  getTodos,
  addTodo,
  toggleTodoDone,
  deleteTodo,
  getCenterAlerts,
  getCenterAlertById,
  getNextPopupCenterAlert,
  markCenterAlertPopupShown,
  updateCenterAlertStatus,
  getCaregiverProfile,
  getDashboardStats,
  refreshCoreState,
  handleRealtimeMessage
}
