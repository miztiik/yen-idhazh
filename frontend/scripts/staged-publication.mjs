/** Which named public files are served, and at which static-relative path? */
const ITEM_FILE = /^[a-z0-9]+(?:-[a-z0-9]+)*-(?:[0-9]{2,}|[0-9a-hjkmnp-tv-z]{16})\.json$/;

/** @param {string} file @param {boolean} servedElsewhere */
export function stagedPath(file, servedElsewhere) {
	if (/^assist\/index\/\d{4}-\d{2}\.(json|bin)$/.test(file)) {
		return `index/${file.slice('assist/index/'.length)}`;
	}
	if (/^digest\/\d{4}\/\d{2}\/\d{2}\/digest\.json$/.test(file)) return file;
	if (file.startsWith('digest/')) {
		return !servedElsewhere && ITEM_FILE.test(file.slice(file.lastIndexOf('/') + 1)) ? file : null;
	}
	return /^(telemetry|console|run-days|day-metrics|machine)\//.test(file) ? file : null;
}
