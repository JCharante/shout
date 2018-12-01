/*
// load session id from storage
sessionId = localStorage.getItem('sessionId') || null

if (sessionId == null) {
    fetch()
}
*/

function getLocation() {
    if(navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(doSomethingWithPosition);
    } else {
        console.log("Geo Location not supported by browser");
    }
}

function generateGoogleMapsLink(longitude, latitude) {
    return `https://www.google.com/maps/place/${latitude},${longitude}`;
}

function generateATag(text, link) {
    return `<a href="${link}">${text}</a>`
}

function doSomethingWithPosition(position) {
    var location = {
        longitude: position.coords.longitude,
        latitude: position.coords.latitude
    };

    let longitude = document.getElementById('longitude');
    let latitude = document.getElementById('latitude');
    let googleMaps = document.getElementById('google-maps');

    longitude.innerHTML = position.coords.longitude;
    latitude.innerHTML = position.coords.latitude;
    googleMaps.innerHTML = generateATag("link", generateGoogleMapsLink(position.coords.longitude, position.coords.latitude));

    console.log(location)
}

function hideSecretCode(code) {
    document.getElementById('secretCodePrompt').innerHTML = '';
}

function showSecretCode(code) {
    function generateHTML () {
        return `<p>Hello, please text <a href="sms://+18509888804">+1 (850) 988-8804</a> with the code ${localStorage.getItem('secretCode')}</p>`
    }
    document.getElementById('secretCodePrompt').innerHTML = generateHTML();
}

function askServerForNewSession() {
    fetch('/web/create_session').then(function(response) {
        return response.json();
    }).then(function(data) {
        jsonData = data;
        localStorage.setItem('sessionId', jsonData.sessionId);
        localStorage.setItem('secretCode', jsonData.secretCode);
        showSecretCode(jsonData.secretCode);
    });
}

function askServerForStatus() {
    fetch('/web/status', {
        method: 'POST',
        body: {
            sessionId: localStorage.getItem('sessionId')
        }
    }).then(function(response) {
        return response.json();
    }).then(function(data) {
        if (data.pairedWithPhoneNumber) {
            hideSecretCode();
        }
    })
}

getLocation();
askServerForNewSession();
setInterval(function() {
    askServerForStatus()
}, 3000);