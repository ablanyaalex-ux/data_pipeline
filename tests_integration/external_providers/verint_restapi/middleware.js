const fs = require('fs');

// NOTE(krishan711): need to filter our responses to only return data for the relevant dates being requested
// json-server doesn't support filtering on nested fields, so we use this middleware to intercept
// adherence requests and filter by adherenceStartDate/adherenceEndDate query params.

var dbData = JSON.parse(fs.readFileSync('/data/db.json', 'utf8'));

module.exports = function(req, res, next) {
  // Detect adherence requests by checking for adherenceStartDate query param
  // (routes.json rewrites /api/adherence to /data before middleware runs)
  var isAdherenceRequest = req.method === 'GET' && req.path === '/data' && req.query.adherenceStartDate;
  
  if (isAdherenceRequest) {
    var startDate = req.query.adherenceStartDate;
    var endDate = req.query.adherenceEndDate;
    
    if (startDate && endDate) {
      var filtered = dbData.data.filter(function(record) {
        var recordStart = record.attributes && record.attributes.adherenceStartDate;
        return recordStart && recordStart >= startDate && recordStart < endDate;
      });
      return res.json({ data: filtered, links: { self: "" } });
    }
    
    return res.json(dbData);
  }
  next();
};
