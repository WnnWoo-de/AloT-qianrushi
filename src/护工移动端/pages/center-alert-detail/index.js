const careService = require('../../services/care-service')
const { syncTodoBadge } = require('../../utils/alert-popup')

function buildContactText(name, phone) {
  return (name || '未设置') + '  ' + (phone || '')
}

Page({
  data: {
    alertId: '',
    entry: 'manual',
    alert: null,
    isHeartRateAlert: false,
    isFallAlert: false,
    statusClass: 'status-waiting',
    emergencyContactText: '',
    nurseText: '',
    topSafeHeight: 0
  },

  onLoad(options) {
    this.setData({
      alertId: options && options.alertId ? options.alertId : '',
      entry: options && options.entry ? options.entry : 'manual',
      topSafeHeight: this.getTopSafeHeight()
    })
    this.loadDetail()
  },

  getTopSafeHeight() {
    try {
      const windowInfo = typeof wx.getWindowInfo === 'function' ? wx.getWindowInfo() : wx.getSystemInfoSync()
      const statusBarHeight = Number(windowInfo.statusBarHeight) || 0
      const menuRect = wx.getMenuButtonBoundingClientRect()
      if (menuRect && menuRect.bottom) {
        const topGap = Math.max(0, Number(menuRect.top) - statusBarHeight)
        return Math.ceil(Number(menuRect.bottom) + topGap + 4)
      }
      return Math.ceil(statusBarHeight + 48)
    } catch (error) {
      return 88
    }
  },

  onShow() {
    this.loadDetail()
    syncTodoBadge()
  },

  async loadDetail() {
    if (!this.data.alertId) {
      return
    }

    try {
      const alert = await careService.getCenterAlertById(this.data.alertId)
      if (!alert) {
        wx.showToast({ title: '报警信息不存在', icon: 'none' })
        return
      }

      const statusClass = alert.status === '已完成' ? 'status-done' : alert.status === '处理中' ? 'status-handling' : 'status-waiting'
      this.setData({
        alert,
        isHeartRateAlert: alert.alertType === '心率异常' || alert.alertType === '生命体征异常',
        isFallAlert: alert.alertType === '跌倒预警' || alert.alertType === '跌倒风险',
        statusClass,
        emergencyContactText: buildContactText(alert.emergencyContactName, alert.emergencyContactPhone),
        nurseText: buildContactText(alert.nurseName, alert.nursePhone)
      })
    } catch (error) {
      wx.showToast({ title: '报警详情加载失败', icon: 'none' })
    }
  },

  makePhoneCall(phoneNumber) {
    if (!phoneNumber) {
      wx.showToast({ title: '联系电话未配置', icon: 'none' })
      return
    }

    let platform = ''
    try {
      if (typeof wx.getDeviceInfo === 'function') {
        platform = wx.getDeviceInfo().platform || ''
      } else {
        platform = wx.getSystemInfoSync().platform || ''
      }
    } catch (error) {}

    if (platform === 'devtools') {
      wx.showModal({
        title: '呼叫联系人',
        content: '拨打 ' + phoneNumber,
        confirmText: '确定',
        cancelText: '取消',
        showCancel: true
      })
      return
    }

    wx.makePhoneCall({
      phoneNumber,
      fail() {
        wx.showToast({ title: '暂时无法发起呼叫', icon: 'none' })
      }
    })
  },

  callEmergencyContact() {
    const alert = this.data.alert
    if (!alert) return
    this.makePhoneCall(alert.emergencyContactPhone)
  },

  callNurse() {
    const alert = this.data.alert
    if (!alert) return
    this.makePhoneCall(alert.nursePhone)
  },

  async acceptAlert() {
    const alert = this.data.alert
    if (!alert || alert.status !== '待响应') return
    try {
      await careService.updateCenterAlertStatus(alert.id, '处理中')
      await this.loadDetail()
      syncTodoBadge()
      wx.showToast({ title: '已进入处理状态', icon: 'success' })
    } catch (error) {
      wx.showToast({ title: '状态更新失败，请重试', icon: 'none' })
    }
  },

  async finishAlert() {
    const alert = this.data.alert
    if (!alert || alert.status === '已完成') return
    try {
      await careService.updateCenterAlertStatus(alert.id, '已完成')
      await this.loadDetail()
      syncTodoBadge()
      wx.showToast({ title: '处置已完成', icon: 'success' })
    } catch (error) {
      wx.showToast({ title: '状态更新失败，请重试', icon: 'none' })
    }
  },

  exitToAlertList() {
    const app = getApp()
    if (app && app.globalData) {
      app.globalData.skipNextIncomingAlertCheck = true
    }
    wx.switchTab({ url: '/pages/todo/index' })
  }
})
