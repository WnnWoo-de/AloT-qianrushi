const { logTypeOptions, moodOptions } = require('../../utils/options')
const careService = require('../../services/care-service')
const { checkIncomingAlertPopup, syncTodoBadge } = require('../../utils/alert-popup')

Page({
  data: {
    elders: [],
    elderIndex: 0,
    targetElderId: '',
    logTypeOptions,
    logTypeIndex: 0,
    moodOptions,
    moodIndex: 0,
    note: '',
    followUp: false
  },

  onLoad(options) {
    this.setData({ targetElderId: options && options.elderId ? options.elderId : '' })
    this.loadElders()
  },

  onShow() {
    syncTodoBadge()
    checkIncomingAlertPopup()
  },

  async loadElders() {
    try {
      const elders = await careService.getElders()
      let elderIndex = 0
      if (this.data.targetElderId) {
        const foundIndex = elders.findIndex(function (item) {
          return item.id === this.data.targetElderId
        }.bind(this))
        if (foundIndex > -1) {
          elderIndex = foundIndex
        }
      }
      this.setData({ elders, elderIndex })
    } catch (error) {
      wx.showToast({ title: '老人信息加载失败', icon: 'none' })
    }
  },

  bindElderChange(event) {
    this.setData({ elderIndex: Number(event.detail.value) })
  },

  bindLogTypeChange(event) {
    this.setData({ logTypeIndex: Number(event.detail.value) })
  },

  bindMoodChange(event) {
    this.setData({ moodIndex: Number(event.detail.value) })
  },

  bindNoteInput(event) {
    this.setData({ note: event.detail.value })
  },

  bindFollowUpChange(event) {
    this.setData({ followUp: event.detail.value })
  },

  async submitForm() {
    const elder = this.data.elders[this.data.elderIndex]
    const type = this.data.logTypeOptions[this.data.logTypeIndex]
    const mood = this.data.moodOptions[this.data.moodIndex]
    const note = (this.data.note || '').trim()

    if (!elder) {
      wx.showToast({ title: '请选择老人', icon: 'none' })
      return
    }
    if (!note) {
      wx.showToast({ title: '请填写护理记录内容', icon: 'none' })
      return
    }

    try {
      await careService.addLog({
        elderId: elder.id,
        elderName: elder.name,
        roomNo: elder.roomNo,
        type,
        mood,
        note,
        followUp: this.data.followUp
      })

      wx.showToast({ title: '日志已保存', icon: 'success' })
      setTimeout(function () {
        wx.redirectTo({ url: '/pages/logs/index' })
      }, 500)
    } catch (error) {
      wx.showToast({ title: '日志保存失败，请重试', icon: 'none' })
    }
  }
})
