const { todoPriorityOptions } = require('../../utils/options')
const careService = require('../../services/care-service')
const { checkIncomingAlertPopup, syncTodoBadge } = require('../../utils/alert-popup')

function withPriorityClass(list) {
  return list.map(function (item) {
    let priorityClass = 'tag-green'
    if (item.priority === '高') {
      priorityClass = 'tag-red'
    } else if (item.priority === '中') {
      priorityClass = 'tag-yellow'
    }

    return Object.assign({}, item, {
      priorityClass,
      doneClass: item.done ? 'done-text' : '',
      doneTagClass: item.done ? 'tag-green' : 'tag-yellow',
      doneText: item.done ? '已完成' : '待处理',
      toggleText: item.done ? '恢复待办' : '标记完成',
      displayMeta: (item.relatedElderName ? '关联老人：' + item.relatedElderName + ' ｜ ' : '') + item.dueText
    })
  })
}

function buildAlertSummary(item) {
  if (item.alertType === '心率异常') {
    return '当前心率 ' + item.heartRateCurrent + ' 次/分钟 ｜ ' + item.abnormalDescription
  }
  if (item.alertType === '跌倒预警') {
    return '识别置信度 ' + item.detectionConfidence + ' ｜ ' + item.monitorSummary
  }
  return item.note
}

function withCenterAlertClass(list) {
  return list.map(function (item) {
    return Object.assign({}, item, {
      statusClass: item.status === '处理中' ? 'tag-yellow' : item.status === '已完成' ? 'tag-green' : 'tag-red',
      summaryText: buildAlertSummary(item)
    })
  })
}

Page({
  data: {
    centerAlerts: [],
    todos: [],
    stats: {
      pendingCenterAlertCount: 0,
      todoPendingCount: 0,
      todoDoneCount: 0
    },
    todoTitle: '',
    dueText: '',
    relatedElderName: '',
    priorityOptions: todoPriorityOptions,
    priorityIndex: 1
  },

  onShow() {
    this.refreshPage()
    syncTodoBadge()
    checkIncomingAlertPopup()
  },

  async refreshPage() {
    try {
      const result = await Promise.all([
        careService.getCenterAlerts({ pendingOnly: true }),
        careService.getTodos(),
        careService.getDashboardStats()
      ])
      this.setData({
        centerAlerts: withCenterAlertClass(result[0]),
        todos: withPriorityClass(result[1]),
        stats: result[2]
      })
    } catch (error) {
      wx.showToast({ title: '任务数据加载失败', icon: 'none' })
    }
  },

  bindTitleInput(event) {
    this.setData({ todoTitle: event.detail.value })
  },

  bindDueInput(event) {
    this.setData({ dueText: event.detail.value })
  },

  bindRelatedElderInput(event) {
    this.setData({ relatedElderName: event.detail.value })
  },

  bindPriorityChange(event) {
    this.setData({ priorityIndex: Number(event.detail.value) })
  },

  async addTodoItem() {
    const title = (this.data.todoTitle || '').trim()
    const dueText = (this.data.dueText || '').trim()
    const relatedElderName = (this.data.relatedElderName || '').trim()
    const priority = this.data.priorityOptions[this.data.priorityIndex]

    if (!title) {
      wx.showToast({ title: '请填写待办内容', icon: 'none' })
      return
    }

    try {
      await careService.addTodo({
        title,
        dueText: dueText || '今日内处理',
        relatedElderName,
        priority
      })
      this.setData({
        todoTitle: '',
        dueText: '',
        relatedElderName: '',
        priorityIndex: 1
      })
      await this.refreshPage()
      wx.showToast({ title: '待办已添加', icon: 'success' })
    } catch (error) {
      wx.showToast({ title: '待办添加失败，请重试', icon: 'none' })
    }
  },

  async toggleTodo(event) {
    const todoId = event.currentTarget.dataset.id
    const item = this.data.todos.find(function (todo) { return todo.id === todoId })
    if (!item) return
    try {
      await careService.toggleTodoDone(todoId, !item.done)
      await this.refreshPage()
    } catch (error) {
      wx.showToast({ title: '待办状态更新失败', icon: 'none' })
    }
  },

  async removeTodo(event) {
    const todoId = event.currentTarget.dataset.id
    try {
      await careService.deleteTodo(todoId)
      await this.refreshPage()
      wx.showToast({ title: '待办已删除', icon: 'none' })
    } catch (error) {
      wx.showToast({ title: '待办删除失败', icon: 'none' })
    }
  },

  async startHandleAlert(event) {
    const alertId = event.currentTarget.dataset.id
    try {
      await careService.updateCenterAlertStatus(alertId, '处理中')
      await this.refreshPage()
      syncTodoBadge()
      wx.showToast({ title: '已进入处理状态', icon: 'success' })
    } catch (error) {
      wx.showToast({ title: '报警状态更新失败', icon: 'none' })
    }
  },

  async finishAlert(event) {
    const alertId = event.currentTarget.dataset.id
    try {
      await careService.updateCenterAlertStatus(alertId, '已完成')
      await this.refreshPage()
      syncTodoBadge()
      wx.showToast({ title: '报警已完成', icon: 'success' })
    } catch (error) {
      wx.showToast({ title: '报警状态更新失败', icon: 'none' })
    }
  },

  viewAlertDetail(event) {
    const alertId = event.currentTarget.dataset.id
    wx.navigateTo({
      url: '/pages/center-alert-detail/index?alertId=' + alertId + '&entry=list'
    })
  }
})
