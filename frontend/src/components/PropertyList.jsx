import React from "react";
import PropertyCard from "./PropertyCard.jsx";

export default function PropertyList({ listings, onSelect }) {
  if (!listings || listings.length === 0) {
    return (
      <div className="listings-pane">
        <h2>Listings</h2>
        <div className="listings-empty">
          Matching properties will show up here once you start chatting.
        </div>
      </div>
    );
  }

  return (
    <div className="listings-pane">
      <h2>{listings.length} listings found</h2>
      <div className="listings-grid">
        {listings.map((l) => (
          <PropertyCard key={l.id} listing={l} onSelect={onSelect} />
        ))}
      </div>
    </div>
  );
}
