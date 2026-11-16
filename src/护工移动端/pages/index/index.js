const careService = require('../../services/care-service')
const { checkIncomingAlertPopup, syncTodoBadge } = require('../../utils/alert-popup')

function withRiskClass(list) {
  return list.map(function (item) {
    let riskClass = 'tag-green'
    if (item.riskLevel === '高风险') {
      riskClass = 'tag-red'
    } else if (item.riskLevel === '中风险') {
      riskClass = 'tag-yellow'
    }
    return Object.assign({}, item, { riskClass })
  })
}

function withAlertStatusClass(list) {
  return list.map(function (item) {
    let statusClass = 'tag-red'
    if (item.status === '已完成') {
      statusClass = 'tag-green'
    } else if (item.status === '处理中') {
      statusClass = 'tag-yellow'
    }
    return Object.assign({}, item, { statusClass })
  })
}

Page({
  data: {
    appName: '银龄卫士护工端',
    intro: '日常照护记录、任务处理与异常事件协同处置。',
    elders: [],
    logs: [],
    centerAlerts: [],
    stats: {
      elderCount: 0,
      todayLogCount: 0,
      needFollowUpCount: 0,
      pendingCenterAlertCount: 0,
      todoPendingCount: 0
    }
  },

  onShow() {
    this.refreshPage()
    syncTodoBadge()
    checkIncomingAlertPopup()
  },

  async refreshPage() {
    try {
      const result = await Promise.all([
        careService.getElders(),
        careService.getLogs(),
        careService.getCenterAlerts(),
        careService.getDashboardStats()
      ])
      this.setData({
        elders: withRiskClass(result[0]),
        logs: result[1].slice(0, 3),
        centerAlerts: withAlertStatusClass(result[2].slice(0, 3)),
        stats: result[3]
      })
    } catch (error) {
      wx.showToast({ title: '数据加载失败，请稍后重试', icon: 'none' })
    }
  },

  goLogs() {
    wx.navigateTo({ url: '/pages/logs/index' })
  },

  goAddLog() {
    wx.navigateTo({ url: '/pages/log-add/index' })
  },

  goEmergency() {
    wx.navigateTo({ url: '/pages/emergency/index' })
  },

  goTodo() {
    wx.switchTab({ url: '/pages/todo/index' })
  },

  goLogForElder(event) {
    const elderId = event.currentTarget.dataset.id
    wx.navigateTo({ url: '/pages/log-add/index?elderId=' + elderId })
  },

  goAlertForElder(event) {
    const elderId = event.currentTarget.dataset.id
    wx.navigateTo({ url: '/pages/emergency/index?elderId=' + elderId })
  }
})
