const terminalCache = require('../runtime/cache/care-mobile')

const LOG_KEY = 'care_logs'
const ALERT_KEY = 'care_alerts'
const TASKS_STORAGE_KEY = 'caregiver_todos'
const CENTER_ALERT_KEY = 'center_alerts'
const PROFILE_KEY = 'caregiver_profile'
const ELDERS_KEY = 'elder_list'
const STATISTICS_KEY = 'care_statistics'
const SERVICE_CACHE_PREFIX = 'service_cache_'
const DATA_VERSION_KEY = 'care_data_version'
const DATA_VERSION = '3.3.0'

function pad(num) {
  return num < 10 ? '0' + num : '' + num
}

function formatDateTime(date) {
  const year = date.getFullYear()
  const month = pad(date.getMonth() + 1)
  const day = pad(date.getDate())
  const hour = pad(date.getHours())
  const minute = pad(date.getMinutes())
  return year + '-' + month + '-' + day + ' ' + hour + ':' + minute
}

function getElderById(elderId) {
  const elders = wx.getStorageSync(ELDERS_KEY) || []
  return elders.find(function (item) {
    return item.id === elderId
  })
}

function getElderByName(name) {
  const elders = wx.getStorageSync(ELDERS_KEY) || []
  return elders.find(function (item) {
    return item.name === name
  })
}

function enrichCenterAlert(payload) {
  const elder = payload.elderId ? getElderById(payload.elderId) : getElderByName(payload.elderName)

  return Object.assign(
    {
      fullScreenRequired: true,
      alertCode: payload.alertCode || String(Date.now()),
      emergencyContactName: payload.emergencyContactName || (elder && elder.emergencyContactName) || '',
      emergencyContactPhone: payload.emergencyContactPhone || (elder && elder.emergencyContactPhone) || '',
      nurseName: payload.nurseName || (elder && elder.nurseName) || '',
      nursePhone: payload.nursePhone || (elder && elder.nursePhone) || '',
      elderAge: payload.elderAge || (elder && elder.age) || '',
      careLevel: payload.careLevel || (elder && elder.careLevel) || '',
      riskLevel: payload.riskLevel || (elder && elder.riskLevel) || ''
    },
    payload
  )
}

function normalizeCenterAlerts(list) {
  return (list || []).map(function (item) {
    return enrichCenterAlert(item)
  })
}

function initializeLocalCache() {
  const dataVersion = wx.getStorageSync(DATA_VERSION_KEY)
  if (dataVersion === DATA_VERSION) return

  const events = Array.isArray(terminalCache.events) ? terminalCache.events : []
  const manualAlerts = events.filter(function (item) {
    return item.channel === 'caregiver' || item.source === 'caregiver'
  })
  const centerAlerts = events.filter(function (item) {
    return item.channel === 'center' || item.source === 'center' || item.source === '智能协同中心'
  })

  wx.setStorageSync(LOG_KEY, Array.isArray(terminalCache.logs) ? terminalCache.logs : [])
  wx.setStorageSync(ALERT_KEY, manualAlerts)
  wx.setStorageSync(TASKS_STORAGE_KEY, Array.isArray(terminalCache.tasks) ? terminalCache.tasks : [])
  wx.setStorageSync(CENTER_ALERT_KEY, normalizeCenterAlerts(centerAlerts))
  wx.setStorageSync(ELDERS_KEY, Array.isArray(terminalCache.elders) ? terminalCache.elders : [])
  wx.setStorageSync(PROFILE_KEY, terminalCache.profile || {})
  wx.removeStorageSync(STATISTICS_KEY)
  wx.setStorageSync(DATA_VERSION_KEY, DATA_VERSION)
}

function getElders() {
  initializeLocalCache()
  return wx.getStorageSync(ELDERS_KEY) || []
}

function getLogs() {
  initializeLocalCache()
  return wx.getStorageSync(LOG_KEY) || []
}

function addLog(payload) {
  const logs = getLogs()
  const item = Object.assign({
    id: 'log-' + Date.now(),
    createdAt: formatDateTime(new Date())
  }, payload)
  logs.unshift(item)
  wx.setStorageSync(LOG_KEY, logs)
  return item
}

function getAlerts() {
  initializeLocalCache()
  return wx.getStorageSync(ALERT_KEY) || []
}

function addAlert(payload) {
  const alerts = getAlerts()
  const item = Object.assign({
    id: 'alert-' + Date.now(),
    status: '已上报',
    createdAt: formatDateTime(new Date())
  }, payload)
  alerts.unshift(item)
  wx.setStorageSync(ALERT_KEY, alerts)
  return item
}

function getTodos() {
  initializeLocalCache()
  return wx.getStorageSync(TASKS_STORAGE_KEY) || []
}

function addTodo(payload) {
  const todos = getTodos()
  const item = Object.assign({
    id: 'todo-' + Date.now(),
    done: false,
    createdAt: formatDateTime(new Date())
  }, payload)
  todos.unshift(item)
  wx.setStorageSync(TASKS_STORAGE_KEY, todos)
  return item
}

function toggleTodoDone(todoId) {
  const todos = getTodos().map(function (item) {
    if (item.id === todoId) {
      return Object.assign({}, item, { done: !item.done })
    }
    return item
  })
  wx.setStorageSync(TASKS_STORAGE_KEY, todos)
  return todos
}

function deleteTodo(todoId) {
  const todos = getTodos().filter(function (item) {
    return item.id !== todoId
  })
  wx.setStorageSync(TASKS_STORAGE_KEY, todos)
  return todos
}

function getCenterAlerts() {
  initializeLocalCache()
  return normalizeCenterAlerts(wx.getStorageSync(CENTER_ALERT_KEY) || [])
}

function getCenterAlertById(alertId) {
  return getCenterAlerts().find(function (item) {
    return item.id === alertId
  }) || null
}

function getPendingCenterAlerts() {
  return getCenterAlerts().filter(function (item) {
    return item.status !== '已完成'
  })
}

function getNextPopupCenterAlert() {
  return getCenterAlerts().find(function (item) {
    return !item.popupShown && item.status !== '已完成'
  })
}

function markCenterAlertPopupShown(alertId) {
  const alerts = getCenterAlerts().map(function (item) {
    if (item.id === alertId) {
      return Object.assign({}, item, { popupShown: true })
    }
    return item
  })
  wx.setStorageSync(CENTER_ALERT_KEY, alerts)
  return alerts
}

function updateCenterAlertStatus(alertId, status) {
  const alerts = getCenterAlerts().map(function (item) {
    if (item.id === alertId) {
      const next = Object.assign({}, item, { status })
      if (status === '已完成') {
        next.handledAt = formatDateTime(new Date())
      }
      return next
    }
    return item
  })
  wx.setStorageSync(CENTER_ALERT_KEY, alerts)
  return alerts
}

function addCenterAlert(payload) {
  const alerts = getCenterAlerts()
  const item = enrichCenterAlert(Object.assign({
    id: 'center-alert-' + Date.now(),
    status: '待响应',
    popupShown: false,
    createdAt: formatDateTime(new Date()),
    source: '智能协同中心',
    assignedTo: (getCaregiverProfile().name || '当班护工'),
    handledAt: ''
  }, payload))
  alerts.unshift(item)
  wx.setStorageSync(CENTER_ALERT_KEY, alerts)
  return item
}

function getCaregiverProfile() {
  initializeLocalCache()
  return wx.getStorageSync(PROFILE_KEY) || {}
}

function isToday(dateText) {
  const today = formatDateTime(new Date()).slice(0, 10)
  return dateText.slice(0, 10) === today
}

function getDashboardStats() {
  const logs = getLogs()
  const alerts = getAlerts()
  const todos = getTodos()
  const centerAlerts = getCenterAlerts()
  let todayLogCount = 0
  let needFollowUpCount = 0
  let todayAlertCount = 0
  let doneTodoCount = 0

  logs.forEach(function (item) {
    if (isToday(item.createdAt)) {
      todayLogCount += 1
    }
    if (item.followUp) {
      needFollowUpCount += 1
    }
  })

  alerts.forEach(function (item) {
    if (isToday(item.createdAt)) {
      todayAlertCount += 1
    }
  })

  todos.forEach(function (item) {
    if (item.done) {
      doneTodoCount += 1
    }
  })

  return {
    elderCount: getElders().length,
    todayLogCount,
    needFollowUpCount,
    todayAlertCount,
    pendingCenterAlertCount: centerAlerts.filter(function (item) {
      return item.status !== '已完成'
    }).length,
    todoPendingCount: todos.filter(function (item) {
      return !item.done
    }).length,
    todoDoneCount: doneTodoCount
  }
}


function replaceElders(list) {
  if (Array.isArray(list) && list.length) wx.setStorageSync(ELDERS_KEY, list)
  return getElders()
}

function replaceLogs(list) {
  if (Array.isArray(list)) wx.setStorageSync(LOG_KEY, list)
  return getLogs()
}

function replaceAlerts(list) {
  if (Array.isArray(list)) wx.setStorageSync(ALERT_KEY, list)
  return getAlerts()
}

function replaceTodos(list) {
  if (Array.isArray(list)) wx.setStorageSync(TASKS_STORAGE_KEY, list)
  return getTodos()
}

function replaceCenterAlerts(list) {
  if (Array.isArray(list)) wx.setStorageSync(CENTER_ALERT_KEY, normalizeCenterAlerts(list))
  return getCenterAlerts()
}

function upsertCenterAlert(payload) {
  const item = enrichCenterAlert(payload)
  const alerts = getCenterAlerts()
  const index = alerts.findIndex(function (entry) { return entry.id === item.id })
  if (index >= 0) alerts[index] = Object.assign({}, alerts[index], item)
  else alerts.unshift(item)
  wx.setStorageSync(CENTER_ALERT_KEY, alerts)
  return item
}

function upsertTodo(payload) {
  const todos = getTodos()
  const index = todos.findIndex(function (entry) { return entry.id === payload.id })
  if (index >= 0) todos[index] = Object.assign({}, todos[index], payload)
  else todos.unshift(payload)
  wx.setStorageSync(TASKS_STORAGE_KEY, todos)
  return payload
}

function setCaregiverProfile(profile) {
  if (profile && profile.id) wx.setStorageSync(PROFILE_KEY, profile)
  return getCaregiverProfile()
}

function getCachedStatistics() {
  return wx.getStorageSync(STATISTICS_KEY) || null
}

function setCachedStatistics(statistics) {
  if (statistics) wx.setStorageSync(STATISTICS_KEY, statistics)
  return getCachedStatistics()
}

function getServiceCache(name) {
  return wx.getStorageSync(SERVICE_CACHE_PREFIX + name) || null
}

function setServiceCache(name, value) {
  if (value !== undefined && value !== null) wx.setStorageSync(SERVICE_CACHE_PREFIX + name, value)
  return getServiceCache(name)
}

module.exports = {
  initializeLocalCache,
  formatDateTime,
  getElders,
  getElderById,
  getLogs,
  addLog,
  getAlerts,
  addAlert,
  getTodos,
  addTodo,
  toggleTodoDone,
  deleteTodo,
  getCenterAlerts,
  getCenterAlertById,
  getPendingCenterAlerts,
  getNextPopupCenterAlert,
  markCenterAlertPopupShown,
  updateCenterAlertStatus,
  addCenterAlert,
  getCaregiverProfile,
  getDashboardStats,
  replaceElders,
  replaceLogs,
  replaceAlerts,
  replaceTodos,
  replaceCenterAlerts,
  upsertCenterAlert,
  upsertTodo,
  setCaregiverProfile,
  getCachedStatistics,
  setCachedStatistics,
  getServiceCache,
  setServiceCache
}
