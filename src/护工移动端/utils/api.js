const transport = require('./request')

function queryString(params) {
  const entries = Object.keys(params || {})
    .filter(function (key) { return params[key] !== undefined && params[key] !== null && params[key] !== '' })
    .map(function (key) { return encodeURIComponent(key) + '=' + encodeURIComponent(params[key]) })
  return entries.length ? '?' + entries.join('&') : ''
}

function get(path, params) {
  return transport.request({ url: path + queryString(params) })
}

function send(path, method, data) {
  return transport.request({ url: path, method, data })
}

module.exports = {
  hasServiceEndpoint: transport.hasServiceEndpoint,
  isServiceAvailable: transport.isServiceAvailable,
  probeService: transport.probeService,
  getSystemStatus: function () { return get('/system/status') },
  getRobots: function () { return get('/robots') },
  getRobotDetail: function (robotId) { return get('/robots/' + encodeURIComponent(robotId)) },
  getTasks: function (params) { return get('/tasks', params) },
  getCurrentTask: function () { return get('/tasks/current') },
  getEvents: function (params) { return get('/events', params) },
  getCurrentEvent: function () { return get('/events/current') },
  getEvent: function (eventId) { return get('/events/' + encodeURIComponent(eventId)) },
  getMap: function () { return get('/map') },
  getStatistics: function () { return get('/statistics') },
  createTask: function (data) { return send('/tasks', 'POST', data) },
  updateTask: function (taskId, data) { return send('/tasks/' + encodeURIComponent(taskId), 'PATCH', data) },
  deleteTask: function (taskId) { return send('/tasks/' + encodeURIComponent(taskId), 'DELETE') },
  createEvent: function (data) { return send('/events', 'POST', data) },
  updateEvent: function (eventId, data) { return send('/events/' + encodeURIComponent(eventId), 'PATCH', data) },
  getElders: function () { return get('/elders') },
  getElder: function (elderId) { return get('/elders/' + encodeURIComponent(elderId)) },
  getCareLogs: function (params) { return get('/care-logs', params) },
  createCareLog: function (data) { return send('/care-logs', 'POST', data) },
  getCaregiverProfile: function () { return get('/caregiver/profile') }
}
