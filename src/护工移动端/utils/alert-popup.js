const careService = require('../services/care-service')
const store = require('./store')

async function syncTodoBadge() {
  try {
    const alerts = store.getPendingCenterAlerts()
    const count = alerts.length
    if (count > 0) {
      wx.setTabBarBadge({
        index: 1,
        text: count > 99 ? '99+' : String(count),
        fail() {}
      })
    } else {
      wx.removeTabBarBadge({
        index: 1,
        fail() {}
      })
    }
  } catch (error) {
    console.error('同步待办角标失败', error)
  }
}

async function checkIncomingAlertPopup() {
  await syncTodoBadge()

  const app = typeof getApp === 'function' ? getApp() : null
  if (app && app.globalData && app.globalData.skipNextIncomingAlertCheck) {
    app.globalData.skipNextIncomingAlertCheck = false
    return
  }

  const pages = typeof getCurrentPages === 'function' ? getCurrentPages() : []
  const current = pages.length ? pages[pages.length - 1] : null
  if (current && current.route === 'pages/center-alert-detail/index') {
    return
  }

  try {
    const nextAlert = store.getNextPopupCenterAlert()
    if (!nextAlert) {
      return
    }

    await careService.markCenterAlertPopupShown(nextAlert.id)

    wx.navigateTo({
      url: '/pages/center-alert-detail/index?alertId=' + nextAlert.id + '&entry=popup',
      fail() {
        wx.redirectTo({
          url: '/pages/center-alert-detail/index?alertId=' + nextAlert.id + '&entry=popup'
        })
      }
    })
  } catch (error) {
    console.error('检查中心报警失败', error)
  }
}

module.exports = {
  syncTodoBadge,
  checkIncomingAlertPopup
}
