const careService = require('../../services/care-service')
const { checkIncomingAlertPopup, syncTodoBadge } = require('../../utils/alert-popup')

Page({
  data: {
    profile: {},
    stats: {
      todayLogCount: 0,
      todoPendingCount: 0,
      pendingCenterAlertCount: 0
    },
    recentCenterAlert: null,
    recentLog: null
  },

  onShow() {
    this.refreshPage()
    syncTodoBadge()
    checkIncomingAlertPopup()
  },

  async refreshPage() {
    try {
      const result = await Promise.all([
        careService.getCaregiverProfile(),
        careService.getDashboardStats(),
        careService.getCenterAlerts(),
        careService.getLogs()
      ])
      let recentCenterAlert = result[2][0] || null
      if (recentCenterAlert) {
        recentCenterAlert = Object.assign({}, recentCenterAlert, {
          statusClass: recentCenterAlert.status === '已完成' ? 'tag-green' : recentCenterAlert.status === '处理中' ? 'tag-yellow' : 'tag-red'
        })
      }
      this.setData({
        profile: result[0],
        stats: result[1],
        recentCenterAlert,
        recentLog: result[3][0] || null
      })
    } catch (error) {
      wx.showToast({ title: '班次信息加载失败', icon: 'none' })
    }
  },

  goEmergency() {
    wx.navigateTo({ url: '/pages/emergency/index' })
  },

  goTodo() {
    wx.switchTab({ url: '/pages/todo/index' })
  },

  goRecentAlertDetail() {
    if (!this.data.recentCenterAlert) {
      return
    }
    wx.navigateTo({
      url: '/pages/center-alert-detail/index?alertId=' + this.data.recentCenterAlert.id + '&entry=manual'
    })
  }
})
