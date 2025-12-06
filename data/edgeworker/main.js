import { httpRequest } from 'http-request';
import { logger } from 'log';

const HARPPER_TOKEN = 'xxxxxxx';
const SUBREQUEST_BASE_URL = 'https://internal-harper-xxx.test.com';

const PMUSER_103_HINTS = 'PMUSER_103_HINTS';
const PMUSER_103_HINTS_ENABLED = 'PMUSER_103_HINTS_ENABLED';



function isSafari(request) {
	return request.device.brandName == 'Safari';
}


export async function onClientRequest(request) {
	let url = `${SUBREQUEST_BASE_URL}/handler?isSafari=${isSafari(request) ? '1' : '0'}`;


	if (request.query !== "") {
  		const params = request.query.split("&");
  		for (const p of params) {
    		const [key, value] = p.split("=");
    		if (key === "v") {
      			url += `&v=${encodeURIComponent(value || "")}`;
    		}
  		}
	}

	const requestHeaders = {
		'Authorization': `Basic ${HARPPER_TOKEN}`,
		'Content-Type': 'application/json',
		'Path': `${request.scheme}://${request.host}${request.url}`,
	};

	const options = {
		timeout: 150,
		method: 'GET',
		headers: requestHeaders,
	};

	const response = await httpRequest(url, options);

	if (response.status == 200) {
		const jsonResponse = await response.json();
		//logger.log('Harper Response Full JSON:', JSON.stringify(jsonResponse, null, 2));

		if (jsonResponse && jsonResponse.redirect) {
				request.respondWith(jsonResponse.redirect.statusCode, { 'location': [jsonResponse.redirect.redirectURL] }, '');
				logger.log('Redirect has been issued by EW to location:', jsonResponse.redirect.redirectURL);
		} else if (jsonResponse && jsonResponse.hints) {
				//logger.log('Early Hints List:', jsonResponse.hints.length);
				request.setVariable(PMUSER_103_HINTS, jsonResponse.hints);
				request.setVariable(PMUSER_103_HINTS_ENABLED,'true');
		}
	}
}