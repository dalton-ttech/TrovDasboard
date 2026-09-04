/* Empty fallback for a fresh checkout. Real history is served from ignored data/history.json. */
window.TROV_DATA = {
  sourceFile: null,
  sheet: null,
  snapshotDate: new Date().toISOString().slice(0, 10),
  timeBasis: 'OMS original timestamp; timezone unspecified',
  shipments: [],
};
