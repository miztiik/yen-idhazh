export function load() {
	return { today: new Date().toISOString().slice(0, 10) };
}
