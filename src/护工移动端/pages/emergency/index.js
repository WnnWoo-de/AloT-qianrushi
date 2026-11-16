const {
  emergencyTypeOptions,
  emergencyLevelOptions
} = require('../../utils/options')
const careService = require('../../services/care-service')
const { checkIncomingAlertPopup, syncTodoBadge } = require('../../utils/alert-popup')

Page({
  data: {
    elders: [],
    targetElderId: '',
    elderIndex: 0,
    emergencyTypeOptions,
    emergencyTypeIndex: 0,
    emergencyLevelOptions,
    emergencyLevelIndex: 0,
    location: '',
    note: '',
    alerts: []
  },

  onLoad(options) {
    this.setData({ targetElderId: options && options.elderId ? options.elderId : '' })
    this.loadBaseData()
  },

  onShow() {
    this.refreshAlerts()
    syncTodoBadge()
    checkIncomingAlertPopup()
  },

  async loadBaseData() {
    try {
      const elders = await careService.getElders()
      let elderIndex = 0
      if (this.data.targetElderId) {
        const foundIndex = elders.findIndex(function (item) {
          return item.id === this.data.targetElderId
        }.bind(this))
        if (foundIndex > -1) elderIndex = foundIndex
      }
      const elder = elders[elderIndex]
      this.setData({
        elders,
        elderIndex,
        location: elder ? elder.roomNo + ' 房间' : ''
      })
    } catch (error) {
      wx.showToast({ title: '老人信息加载失败', icon: 'none' })
    }
  },

  async refreshAlerts() {
    try {
      const alerts = await careService.getManualAlerts()
      this.setData({ alerts })
    } catch (error) {
      wx.showToast({ title: '报警记录加载失败', icon: 'none' })
    }
  },

  bindElderChange(event) {
    const elderIndex = Number(event.detail.value)
    this.setData({
      elderIndex,
      location: this.data.elders[elderIndex].roomNo + ' 房间'
    })
  },

  bindEmergencyTypeChange(event) {
    this.setData({ emergencyTypeIndex: Number(event.detail.value) })
  },

  bindEmergencyLevelChange(event) {
    this.setData({ emergencyLevelIndex: Number(event.detail.value) })
  },

  bindLocationInput(event) {
    this.setData({ location: event.detail.value })
  },

  bindNoteInput(event) {
    this.setData({ note: event.detail.value })
  },

  async triggerAlert() {
    const elder = this.data.elders[this.data.elderIndex]
    const alertType = this.data.emergencyTypeOptions[this.data.emergencyTypeIndex]
    const level = this.data.emergencyLevelOptions[this.data.emergencyLevelIndex]
    const location = (this.data.location || '').trim()
    const note = (this.data.note || '').trim()

    if (!elder) {
      wx.showToast({ title: '请选择老人', icon: 'none' })
      return
    }
    if (!location) {
      wx.showToast({ title: '请填写事发位置', icon: 'none' })
      return
    }

    try {
      await careService.addManualAlert({
        elderId: elder.id,
        elderName: elder.name,
        roomNo: elder.roomNo,
        alertType,
        level,
        location,
        note: note || '护工现场发现异常，已提交紧急报警。'
      })
      this.setData({ note: '' })
      await this.refreshAlerts()
      wx.showModal({
        title: '报警已上报',
        content: '事件已提交至报警中心，相关值班人员将同步收到处置任务。',
        showCancel: false
      })
    } catch (error) {
      wx.showToast({ title: '报警上报失败，请重试', icon: 'none' })
    }
  }
})
