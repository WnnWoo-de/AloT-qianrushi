const apiConfig = require('../config/api')
const serviceStatus = require('./service-status')

function trimSlash(value) {
  return String(value || '').replace(/\/+$/, '')
}

function hasServiceEndpoint() {
  return serviceStatus.hasServiceEndpoint()
}

function isServiceAvailable() {
  return hasServiceEndpoint() && serviceStatus.isOnline()
}

function joinUrl(path) {
  const base = trimSlash(apiConfig.API_BASE_URL)
  const prefix = trimSlash(apiConfig.API_PREFIX)
  const suffix = path.charAt(0) === '/' ? path : '/' + path
  return base + prefix + suffix
}

function request(options) {
  if (!hasServiceEndpoint()) {
    return Promise.reject(new Error('SERVICE_ENDPOINT_UNBOUND'))
  }
  if (!serviceStatus.isOnline()) {
    return Promise.reject(new Error('SERVICE_OFFLINE'))
  }

  return new Promise(function (resolve, reject) {
    const token = wx.getStorageSync('access_token') || ''
    const headers = Object.assign(
      { 'content-type': 'application/json' },
      token ? { Authorization: 'Bearer ' + token } : {},
      options.header || {}
    )

    wx.request({
      url: joinUrl(options.url),
      method: options.method || 'GET',
      data: options.data || {},
      header: headers,
      timeout: apiConfig.TIMEOUT,
      success(res) {
        serviceStatus.markOnline()
        if (res.statusCode < 200 || res.statusCode >= 300) {
          reject(new Error((res.data && res.data.message) || 'HTTP_' + res.statusCode))
          return
        }

        const body = res.data
        if (body && typeof body === 'object' && Object.prototype.hasOwnProperty.call(body, 'code')) {
          if (body.code !== 0) {
            reject(new Error(body.message || 'BUSINESS_ERROR'))
            return
          }
          resolve(body.data)
          return
        }

        resolve(body)
      },
      fail(error) {
        serviceStatus.markOffline()
        reject(error)
      }
    })
  })
}

module.exports = {
  request,
  hasServiceEndpoint,
  isServiceAvailable,
  probeService: serviceStatus.probeService,
  joinUrl
}
