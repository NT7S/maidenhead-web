/*
 * Maidenhead grid locator conversions (browser version).
 *
 * This is a direct port of grid.py so the static site can convert locally,
 * with no backend.  A locator is built from:
 *   1. two field letters A-R (18 columns/rows, 20 deg lon x 10 deg lat)
 *   2. two square digits 0-9 (2 deg lon x 1 deg lat)
 *   3. optionally two subsquare letters A-X (5 min lon x 2.5 min lat)
 *
 * gridToLatLon returns the center of the square.  latLonToGrid uses floor
 * semantics at cell boundaries and clamps the exact +90/+180 edge to the last
 * valid cell.
 */
(function (global) {
  "use strict";

  var LAST_FIELD = "R";
  var LAST_SUBSQUARE = "X";

  function letterIndex(ch, last) {
    var value = ch.charCodeAt(0) - 65;
    if (!(value >= 0 && value <= last.charCodeAt(0) - 65)) {
      throw new Error("invalid letter " + JSON.stringify(ch));
    }
    return value;
  }

  function normalizeGrid(grid) {
    if (typeof grid !== "string") {
      throw new Error("grid locator must be a string");
    }
    var g = grid.trim().toUpperCase();
    if (g.length !== 4 && g.length !== 6) {
      throw new Error(
        "grid locator must be 4 or 6 characters, got " + g.length
      );
    }
    if (!/[0-9]/.test(g.charAt(2)) || !/[0-9]/.test(g.charAt(3))) {
      throw new Error("square digits must be 0-9");
    }
    // Validate letters by computing them; letterIndex throws on bad input.
    letterIndex(g.charAt(0), LAST_FIELD);
    letterIndex(g.charAt(1), LAST_FIELD);
    if (g.length === 6) {
      letterIndex(g.charAt(4), LAST_SUBSQUARE);
      letterIndex(g.charAt(5), LAST_SUBSQUARE);
    }
    return g.slice(0, 4).toUpperCase() + g.slice(4).toLowerCase();
  }

  function gridToLatLon(grid) {
    // normalizeGrid returns the canonical form with lowercase subsquares;
    // the math below indexes letters by uppercase ordinal.
    var g = normalizeGrid(grid).toUpperCase();

    var lonField = letterIndex(g.charAt(0), LAST_FIELD);
    var latField = letterIndex(g.charAt(1), LAST_FIELD);
    var lonSquare = Number(g.charAt(2));
    var latSquare = Number(g.charAt(3));

    var lon = -180.0 + 20.0 * lonField + 2.0 * lonSquare;
    var lat = -90.0 + 10.0 * latField + 1.0 * latSquare;

    if (g.length === 4) {
      return { lat: lat + 0.5, lon: lon + 1.0 };
    }

    var lonSub = letterIndex(g.charAt(4), LAST_SUBSQUARE);
    var latSub = letterIndex(g.charAt(5), LAST_SUBSQUARE);
    lon += (5.0 / 60.0) * (lonSub + 0.5);
    lat += (2.5 / 60.0) * (latSub + 0.5);
    return { lat: lat, lon: lon };
  }

  function latLonToGrid(lat, lon, precision) {
    if (precision === undefined) {
      precision = 6;
    }
    if (precision !== 4 && precision !== 6) {
      throw new Error("precision must be 4 or 6");
    }

    var latF = Number(lat);
    var lonF = Number(lon);
    if (Number.isNaN(latF) || Number.isNaN(lonF)) {
      throw new Error("latitude and longitude must be numbers");
    }
    if (!Number.isFinite(latF) || !Number.isFinite(lonF)) {
      throw new Error("latitude and longitude must be finite");
    }
    if (!(latF >= -90.0 && latF <= 90.0)) {
      throw new Error("latitude must be between -90 and 90");
    }
    if (!(lonF >= -180.0 && lonF <= 180.0)) {
      throw new Error("longitude must be between -180 and 180");
    }

    latF = Math.min(89.999999999, latF);
    lonF = Math.min(179.999999999, lonF);

    var lonShift = lonF + 180.0;
    var latShift = latF + 90.0;

    var lonField = Math.min(17, Math.floor(lonShift / 20.0));
    var latField = Math.min(17, Math.floor(latShift / 10.0));
    var lonRem = lonShift - 20.0 * lonField;
    var latRem = latShift - 10.0 * latField;

    var lonSquare = Math.min(9, Math.floor(lonRem / 2.0));
    var latSquare = Math.min(9, Math.floor(latRem / 1.0));
    var lonSub = Math.min(
      23,
      Math.floor((lonRem - 2.0 * lonSquare) * 12.0)
    );
    var latSub = Math.min(23, Math.floor((latRem - 1.0 * latSquare) * 24.0));

    var locator =
      String.fromCharCode(65 + lonField) +
      String.fromCharCode(65 + latField) +
      lonSquare +
      latSquare;
    if (precision === 6) {
      locator +=
        String.fromCharCode(97 + lonSub) + String.fromCharCode(97 + latSub);
    }
    return locator;
  }

  global.Maidenhead = {
    latLonToGrid: latLonToGrid,
    gridToLatLon: gridToLatLon,
    normalizeGrid: normalizeGrid,
    isValidGrid: function (grid) {
      try {
        normalizeGrid(grid);
        return true;
      } catch (error) {
        return false;
      }
    },
    isValidLatLon: function (lat, lon) {
      var latF = Number(lat);
      var lonF = Number(lon);
      return (
        Number.isFinite(latF) &&
        Number.isFinite(lonF) &&
        latF >= -90 &&
        latF <= 90 &&
        lonF >= -180 &&
        lonF <= 180
      );
    },
  };
})(typeof window !== "undefined" ? window : this);
