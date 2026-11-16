const careService = require('../../services/care-service')
const { checkIncomingAlertPopup, syncTodoBadge } = require('../../utils/alert-popup')

Page({
  data: {
    elderFilters: [],
    activeElderId: 'all',
    logs: [],
    displayLogs: []
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
        careService.getLogs()
      ])
      const elderFilters = [{ id: 'all', name: '全部' }].concat(
        result[0].map(function (item) {
          return { id: item.id, name: item.name }
        })
      )
      this.setData({ elderFilters, logs: result[1] })
      this.applyFilter(this.data.activeElderId, result[1])
    } catch (error) {
      wx.showToast({ title: '护理日志加载失败', icon: 'none' })
    }
  },

  setFilter(event) {
    const elderId = event.currentTarget.dataset.id
    this.setData({ activeElderId: elderId })
    this.applyFilter(elderId, this.data.logs)
  },

  applyFilter(elderId, logs) {
    let displayLogs = logs
    if (elderId !== 'all') {
      displayLogs = logs.filter(function (item) {
        return item.elderId === elderId
      })
    }
    this.setData({ displayLogs })
  },

  goAddLog() {
    wx.navigateTo({ url: '/pages/log-add/index' })
  }
})
