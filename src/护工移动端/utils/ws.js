const apiConfig = require('../config/api')

function trimSlash(value) {
  return String(value || '').replace(/\/+$/, '')
}

function hasRealtimeEndpoint() {
  return Boolean(trimSlash(apiConfig.WS_BASE_URL))
}

function connectMonitor(onMessage, onDisconnect) {
  if (!hasRealtimeEndpoint()) return null

  const socket = wx.connectSocket({
    url: trimSlash(apiConfig.WS_BASE_URL) + '/ws/monitor'
  })

  socket.onMessage(function (event) {
    try {
      const message = JSON.parse(event.data)
      if (message && message.type && Object.prototype.hasOwnProperty.call(message, 'data')) {
        onMessage && onMessage(message)
      }
    } catch (error) {}
  })

  socket.onClose(function () {
    onDisconnect && onDisconnect()
  })

  socket.onError(function () {
    onDisconnect && onDisconnect()
  })

  return socket
}

module.exports = {
  hasRealtimeEndpoint,
  connectMonitor
}
