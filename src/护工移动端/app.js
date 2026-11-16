const apiConfig = require('./config/api')
const { initializeLocalCache } = require('./utils/store')
const { syncTodoBadge } = require('./utils/alert-popup')
const { connectMonitor } = require('./utils/ws')
const careService = require('./services/care-service')

App({
  globalData: {
    appName: '银龄卫士护工端',
    version: '3.0.0',
    skipNextIncomingAlertCheck: false,
    monitorSocket: null,
    recoveryTimer: null
  },

  onLaunch() {
    initializeLocalCache()
    syncTodoBadge()
  },

  onShow() {
    this.resumeServiceSync()
  },

  onHide() {
    this.clearRecoveryTimer()
  },

  resumeServiceSync() {
    const app = this
    return careService.probeService(true).then(function (available) {
      if (!available) {
        app.scheduleRecovery()
        return false
      }

      app.clearRecoveryTimer()
      return careService.refreshCoreState().then(function () {
        syncTodoBadge()
        if (!careService.isServiceAvailable()) {
          app.scheduleRecovery()
          return false
        }
        app.startMonitor()
        return true
      })
    })
  },

  startMonitor() {
    if (this.globalData.monitorSocket || !careService.isServiceAvailable()) return

    const app = this
    this.globalData.monitorSocket = connectMonitor(function (message) {
      careService.handleRealtimeMessage(message)
      if (message.type === 'event_update' || message.type === 'task_update') {
        syncTodoBadge()
      }
    }, function () {
      app.globalData.monitorSocket = null
      app.scheduleRecovery()
    })
  },

  scheduleRecovery() {
    if (this.globalData.recoveryTimer) return
    const app = this
    this.globalData.recoveryTimer = setTimeout(function () {
      app.globalData.recoveryTimer = null
      app.resumeServiceSync()
    }, apiConfig.OFFLINE_RETRY_INTERVAL || 30000)
  },

  clearRecoveryTimer() {
    if (!this.globalData.recoveryTimer) return
    clearTimeout(this.globalData.recoveryTimer)
    this.globalData.recoveryTimer = null
  },

  updateTodoBadge() {
    return syncTodoBadge()
  }
})
