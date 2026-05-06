import React from "react";

/**
 * Placeholder for a Mapbox view. Drop in `mapbox-gl` and use VITE_MAPBOX_TOKEN
 * to turn this into a real map of the listings' lat/lng.
 */
export default function MapView({ listings }) {
  if (!listings || listings.length === 0) return null;
  return (
    <div style={{ padding: 20, color: "#9ca3af" }}>
      Map view placeholder. Install <code>mapbox-gl</code> to plot {listings.length}{" "}
      listings.
    </div>
  );
}
