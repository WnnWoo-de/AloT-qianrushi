const apiConfig = require('../config/api')

let status = 'unknown'
let checking = null
let lastCheckedAt = 0

function trimSlash(value) {
  return String(value || '').replace(/\/+$/, '')
}

function hasServiceEndpoint() {
  return Boolean(trimSlash(apiConfig.API_BASE_URL))
}

function healthUrl() {
  const base = trimSlash(apiConfig.API_BASE_URL)
  const prefix = trimSlash(apiConfig.API_PREFIX)
  return base + prefix + '/health'
}

function markOnline() {
  status = 'online'
  lastCheckedAt = Date.now()
}

function markOffline() {
  status = 'offline'
  lastCheckedAt = Date.now()
}

function isOnline() {
  return status === 'online'
}

function getStatus() {
  return {
    status,
    lastCheckedAt
  }
}

function probeService(force) {
  if (!hasServiceEndpoint()) {
    markOffline()
    return Promise.resolve(false)
  }

  if (checking) return checking
  if (!force && isOnline()) return Promise.resolve(true)

  checking = new Promise(function (resolve) {
    wx.request({
      url: healthUrl(),
      method: 'GET',
      timeout: apiConfig.HEALTH_TIMEOUT || 1200,
      success(res) {
        const body = res.data
        const healthy = res.statusCode >= 200 && res.statusCode < 300 && (!body || body.code === undefined || body.code === 0)
        if (healthy) markOnline()
        else markOffline()
        resolve(healthy)
      },
      fail() {
        markOffline()
        resolve(false)
      }
    })
  }).then(function (available) {
    checking = null
    return available
  })

  return checking
}

module.exports = {
  hasServiceEndpoint,
  isOnline,
  getStatus,
  markOnline,
  markOffline,
  probeService
}
