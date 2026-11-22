/**
 * Villa La Roccia del Poggio - fills the "Booked" column (C) of the price sheet
 * with A (Airbnb) and V (Vrbo) bookings, every hour.
 *
 * It only writes in cells that are empty or already contain A or V:
 * anything you type yourself (W for a direct booking, or a note) is never touched.
 * If an Airbnb/Vrbo booking is cancelled, its A / V is removed at the next update.
 *
 * One-time setup (in the Google Sheet):
 *   Extensions -> Apps Script -> delete everything -> paste this file -> Save (disk icon)
 *   choose the function "setup" at the top -> Run -> allow access when Google asks.
 */

var STATUS_URL = 'https://larocciadelpoggio.github.io/lrp-calendar/status.csv';
var SHEET_NAME = 'Prices';
var FIRST_ROW = 9;      // first date row
var DATE_COL = 1;       // A
var BOOKED_COL = 3;     // C

function updateBookings() {
  var resp = UrlFetchApp.fetch(STATUS_URL + '?t=' + Date.now(), { muteHttpExceptions: true });
  if (resp.getResponseCode() !== 200) {
    console.log('Could not read ' + STATUS_URL + ' (HTTP ' + resp.getResponseCode() + ')');
    return;
  }
  // line: day number, Airbnb status, Vrbo status, yyyy-mm-dd
  var code = {};
  resp.getContentText().split(/\r?\n/).forEach(function (line) {
    var p = line.split(',');
    if (p.length < 4) return;
    if (p[1] === 'Booked') code[p[3]] = 'A';
    else if (p[2] === 'Booked') code[p[3]] = 'V';
  });

  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName(SHEET_NAME);
  var n = sh.getLastRow() - FIRST_ROW + 1;
  if (n < 1) return;
  var tz = ss.getSpreadsheetTimeZone();
  var dates = sh.getRange(FIRST_ROW, DATE_COL, n, 1).getValues();
  var range = sh.getRange(FIRST_ROW, BOOKED_COL, n, 1);
  var vals = range.getValues();
  var changed = 0;
  for (var i = 0; i < n; i++) {
    var d = dates[i][0];
    if (!(d instanceof Date)) continue;
    var cur = String(vals[i][0]).trim().toUpperCase();
    if (cur !== '' && cur !== 'A' && cur !== 'V') continue;   // typed by you: leave it
    var want = code[Utilities.formatDate(d, tz, 'yyyy-MM-dd')] || '';
    if (cur !== want) { vals[i][0] = want; changed++; }
  }
  if (changed) range.setValues(vals);
  console.log('Booked column updated: ' + changed + ' cell(s) changed');
}

/** Run once: creates the hourly update and runs it immediately. */
function setup() {
  ScriptApp.getProjectTriggers().forEach(function (t) { ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('updateBookings').timeBased().everyHours(1).create();
  updateBookings();
}
