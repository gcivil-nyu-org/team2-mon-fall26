(() => {
  "use strict";

  const dataElement = document.getElementById("map-data");
  const mapElement = document.getElementById("hotspot-map");
  if (!dataElement || !mapElement) return;

  const profileOnly = mapElement.dataset.profileOnly === "true";
  const parsed = JSON.parse(dataElement.textContent);
  const hotspots = (Array.isArray(parsed) ? parsed : [parsed]).filter(Boolean);
  const chooser = document.getElementById("hotspot-select");
  const notice = document.getElementById("map-notice");
  const markers = new Map();
  let map;
  let selectedMarker;

  function showNotice(message) {
    if (!notice) return;
    notice.textContent = message;
    notice.hidden = false;
  }

  function setText(id, value, fallback = "Not provided") {
    const element = document.getElementById(id);
    if (element) element.textContent = value || fallback;
  }

  function selectHotspot(hotspot, panToMarker = false) {
    if (!profileOnly) {
      setText("preview-name", hotspot.name);
      setText("preview-location", hotspot.location, "Location details not provided");
      setText("preview-borough", hotspot.borough);
      setText("preview-provider", hotspot.provider);
      setText("preview-type", hotspot.location_type);
      setText("preview-access", hotspot.access_type);
      setText("preview-ssid", hotspot.ssid);
      document.getElementById("preview-profile-link").href = hotspot.profile_url;
      if (chooser) chooser.value = String(hotspot.id);

      const rating = document.getElementById("preview-rating");
      rating.replaceChildren();
      if (hotspot.rating_count && hotspot.average_rating !== null) {
        const star = document.createElement("span");
        star.className = "star";
        star.setAttribute("aria-hidden", "true");
        star.textContent = "★ ";
        rating.append(star, `${Number(hotspot.average_rating).toFixed(1)} / 5`);
        const count = document.createElement("span");
        count.className = "rating-count";
        count.textContent = `(${hotspot.rating_count} rating${hotspot.rating_count === 1 ? "" : "s"})`;
        rating.append(count);
      } else {
        rating.textContent = "No ratings yet";
      }
      document.getElementById("preview-demo-label").hidden = !hotspot.has_demo_reviews;
    }

    if (selectedMarker?.getElement()) selectedMarker.getElement().classList.remove("is-selected");
    selectedMarker = markers.get(String(hotspot.id));
    if (selectedMarker?.getElement()) selectedMarker.getElement().classList.add("is-selected");
    if (map && selectedMarker && panToMarker) {
      map.setView(selectedMarker.getLatLng(), Math.max(map.getZoom(), 14), { animate: false });
      selectedMarker.openPopup();
    }
  }

  if (chooser) {
    const labels = new Map();
    for (const hotspot of hotspots) {
      const label = `${hotspot.name} — ${hotspot.borough}`;
      labels.set(label, (labels.get(label) || 0) + 1);
    }
    for (const option of chooser.options) {
      const hotspot = hotspots.find((item) => String(item.id) === option.value);
      if (!hotspot) continue;
      const label = `${hotspot.name} — ${hotspot.borough}`;
      option.textContent = labels.get(label) > 1 ? `${label} (Record ${hotspot.id})` : label;
    }
    chooser.addEventListener("change", () => {
      const hotspot = hotspots.find((item) => String(item.id) === chooser.value);
      if (hotspot) selectHotspot(hotspot, true);
    });
  }
  document.documentElement.classList.add("js");

  if (!window.L) {
    showNotice("The map could not load. Choose a hotspot or browse the profiles below to view its details.");
    if (hotspots[0]) selectHotspot(hotspots[0]);
    return;
  }

  map = L.map(mapElement, { scrollWheelZoom: false, zoomControl: true, attributionControl: true });
  map.zoomControl.setPosition("bottomright");
  if (mapElement.dataset.tileUrl) {
    L.tileLayer(mapElement.dataset.tileUrl, {
      attribution: mapElement.dataset.tileAttribution,
      maxZoom: 19,
    }).on("tileerror", () => {
      showNotice("Some map tiles could not load. You can still choose a hotspot and open its profile.");
    }).addTo(map);
  } else {
    showNotice("Map tiles are unavailable. Hotspot locations and profiles are still available.");
  }

  const icon = L.divIcon({ className: "hotspot-marker", html: '<span class="map-pin"></span>', iconSize: [28, 32], iconAnchor: [14, 28], popupAnchor: [0, -22] });
  const groups = new Map();
  for (const hotspot of hotspots) {
    const latitude = Number(hotspot.latitude);
    const longitude = Number(hotspot.longitude);
    if (hotspot.latitude == null || hotspot.longitude == null || !Number.isFinite(latitude) || !Number.isFinite(longitude) || Math.abs(latitude) > 90 || Math.abs(longitude) > 180) continue;
    const key = `${latitude},${longitude}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(hotspot);
  }

  for (const group of groups.values()) {
    const first = group[0];
    const title = group.length > 1 ? `${first.name}: ${group.length} hotspots at this location` : first.name;
    const marker = L.marker([Number(first.latitude), Number(first.longitude)], { icon, title, alt: title, keyboard: true, riseOnHover: true }).addTo(map);
    const popup = document.createElement("div");
    popup.className = "hotspot-popup";
    const popupTitle = document.createElement("div");
    popupTitle.className = "hotspot-popup-title";
    popupTitle.textContent = group.length > 1 ? "Hotspots at this location" : first.name;
    popup.append(popupTitle);

    if (group.length > 1 && !profileOnly) {
      for (const hotspot of group) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "popup-hotspot-choice";
        button.textContent = hotspot.name;
        const description = document.createElement("small");
        description.textContent = [`Record ${hotspot.id}`, hotspot.provider, hotspot.ssid].filter(Boolean).join(" · ");
        button.append(description);
        button.addEventListener("click", () => selectHotspot(hotspot));
        popup.append(button);
      }
    } else {
      const location = document.createElement("p");
      location.className = "hotspot-popup-location";
      location.textContent = first.location || first.borough;
      popup.append(location);
      if (!profileOnly) {
        const link = document.createElement("a");
        link.href = first.profile_url;
        link.textContent = "View hotspot profile";
        popup.append(link);
      }
    }
    marker.bindPopup(popup, { maxWidth: 260 });
    marker.on("click", () => selectHotspot(first));
    for (const hotspot of group) markers.set(String(hotspot.id), marker);
  }

  const uniqueMarkers = [...new Set(markers.values())];
  if (uniqueMarkers.length === 1) {
    map.setView(uniqueMarkers[0].getLatLng(), 15);
  } else if (uniqueMarkers.length > 1) {
    map.fitBounds(L.featureGroup(uniqueMarkers).getBounds(), { padding: [35, 35], maxZoom: 14 });
  } else {
    map.setView([40.73, -73.97], 11);
    showNotice("These records have no map coordinates. Browse the profiles to view their location information.");
  }
  if (hotspots[0]) selectHotspot(hotspots[0]);
})();
