/** Which explicit query-door session owns the page's cached answers? */
let session = Symbol('ledger read session');

export function readSession(): symbol {
	return session;
}

export function renewReadSession(): void {
	session = Symbol('ledger read session');
}
