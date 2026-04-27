import streamlit as st
import pandas as pd
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
import uuid


class ShipmentStatus(Enum):
    REQUESTED = "Requested"
    APPROVED = "Approved"
    DISPATCHED = "Dispatched"
    DELIVERED = "Delivered"
    CANCELLED = "Cancelled"


@dataclass
class Item:
    item_id: str
    name: str
    unit: str


@dataclass
class Location:
    location_id: str
    name: str
    location_type: str
    address: str


@dataclass
class Vehicle:
    vehicle_id: str
    plate_number: str
    capacity_kg: float
    available: bool = True


@dataclass
class ShipmentItem:
    item_id: str
    quantity: float
    weight_kg: float


@dataclass
class Shipment:
    shipment_id: str
    source_id: str
    destination_id: str
    items: List[ShipmentItem]
    status: ShipmentStatus
    requested_at: datetime
    approved_at: Optional[datetime] = None
    dispatched_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    vehicle_id: Optional[str] = None
    notes: str = ""


class LogisticsSystem:
    def __init__(self):
        self.items: Dict[str, Item] = {}
        self.locations: Dict[str, Location] = {}
        self.vehicles: Dict[str, Vehicle] = {}
        self.inventory: Dict[str, Dict[str, float]] = {}
        self.shipments: Dict[str, Shipment] = {}

    def generate_id(self, prefix):
        return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"

    def add_item(self, name, unit):
        item_id = self.generate_id("ITEM")
        self.items[item_id] = Item(item_id, name, unit)
        return item_id

    def add_location(self, name, location_type, address):
        location_id = self.generate_id("LOC")
        self.locations[location_id] = Location(location_id, name, location_type, address)
        self.inventory[location_id] = {}
        return location_id

    def add_vehicle(self, plate_number, capacity_kg):
        vehicle_id = self.generate_id("VEH")
        self.vehicles[vehicle_id] = Vehicle(vehicle_id, plate_number, capacity_kg)
        return vehicle_id

    def add_stock(self, location_id, item_id, quantity):
        self.inventory[location_id][item_id] = self.inventory[location_id].get(item_id, 0) + quantity

    def remove_stock(self, location_id, item_id, quantity):
        available = self.inventory[location_id].get(item_id, 0)
        if available < quantity:
            raise ValueError(f"Insufficient stock. Available: {available}, Requested: {quantity}")
        self.inventory[location_id][item_id] -= quantity

    def create_shipment(self, source_id, destination_id, items, notes):
        if source_id == destination_id:
            raise ValueError("Source and destination cannot be the same.")

        for item in items:
            available = self.inventory[source_id].get(item.item_id, 0)
            if available < item.quantity:
                raise ValueError("Insufficient stock for one or more items.")

        shipment_id = self.generate_id("SHIP")
        self.shipments[shipment_id] = Shipment(
            shipment_id=shipment_id,
            source_id=source_id,
            destination_id=destination_id,
            items=items,
            status=ShipmentStatus.REQUESTED,
            requested_at=datetime.now(),
            notes=notes,
        )
        return shipment_id

    def approve_shipment(self, shipment_id):
        shipment = self.shipments[shipment_id]
        if shipment.status != ShipmentStatus.REQUESTED:
            raise ValueError("Only requested shipments can be approved.")
        shipment.status = ShipmentStatus.APPROVED
        shipment.approved_at = datetime.now()

    def assign_vehicle(self, shipment_id):
        shipment = self.shipments[shipment_id]
        if shipment.status != ShipmentStatus.APPROVED:
            raise ValueError("Approve shipment before assigning vehicle.")

        total_weight = sum(i.weight_kg for i in shipment.items)

        for vehicle in self.vehicles.values():
            if vehicle.available and vehicle.capacity_kg >= total_weight:
                vehicle.available = False
                shipment.vehicle_id = vehicle.vehicle_id
                return vehicle.vehicle_id

        raise ValueError("No available vehicle with enough capacity.")

    def dispatch_shipment(self, shipment_id):
        shipment = self.shipments[shipment_id]
        if shipment.status != ShipmentStatus.APPROVED:
            raise ValueError("Only approved shipments can be dispatched.")
        if not shipment.vehicle_id:
            raise ValueError("Assign vehicle before dispatch.")

        for item in shipment.items:
            self.remove_stock(shipment.source_id, item.item_id, item.quantity)

        shipment.status = ShipmentStatus.DISPATCHED
        shipment.dispatched_at = datetime.now()

    def deliver_shipment(self, shipment_id):
        shipment = self.shipments[shipment_id]
        if shipment.status != ShipmentStatus.DISPATCHED:
            raise ValueError("Only dispatched shipments can be delivered.")

        for item in shipment.items:
            self.add_stock(shipment.destination_id, item.item_id, item.quantity)

        shipment.status = ShipmentStatus.DELIVERED
        shipment.delivered_at = datetime.now()

        if shipment.vehicle_id:
            self.vehicles[shipment.vehicle_id].available = True

    def cancel_shipment(self, shipment_id):
        shipment = self.shipments[shipment_id]
        if shipment.status in [ShipmentStatus.DISPATCHED, ShipmentStatus.DELIVERED]:
            raise ValueError("Cannot cancel dispatched or delivered shipments.")
        shipment.status = ShipmentStatus.CANCELLED


def init_system():
    if "system" not in st.session_state:
        system = LogisticsSystem()

        warehouse = system.add_location("Main Office Warehouse", "Warehouse", "Main City")
        site_a = system.add_location("Site A", "Site", "North Zone")
        site_b = system.add_location("Site B", "Site", "South Zone")

        cement = system.add_item("Cement Bags", "bags")
        steel = system.add_item("Steel Rods", "pieces")
        bricks = system.add_item("Bricks", "pieces")

        system.add_vehicle("TRK-1001", 5000)
        system.add_vehicle("TRK-1002", 3000)

        system.add_stock(warehouse, cement, 500)
        system.add_stock(warehouse, steel, 200)
        system.add_stock(warehouse, bricks, 10000)

        st.session_state.system = system


def location_options(system):
    return {f"{loc.name} ({loc.location_type})": loc_id for loc_id, loc in system.locations.items()}


def item_options(system):
    return {f"{item.name} ({item.unit})": item_id for item_id, item in system.items.items()}


def shipment_options(system):
    return {f"{sid} - {s.status.value}": sid for sid, s in system.shipments.items()}


st.set_page_config(page_title="Logistics Management System", layout="wide")
init_system()
system = st.session_state.system

st.title("🚚 Logistics Management System")
st.caption("Warehouse ↔ Sites | Site ↔ Site material movement")

menu = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard",
        "Locations",
        "Items",
        "Vehicles",
        "Inventory",
        "Create Shipment",
        "Manage Shipments",
        "Reports",
    ],
)

if menu == "Dashboard":
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Locations", len(system.locations))
    col2.metric("Items", len(system.items))
    col3.metric("Vehicles", len(system.vehicles))
    col4.metric("Shipments", len(system.shipments))

    st.subheader("Recent Shipments")

    data = []
    for s in system.shipments.values():
        data.append({
            "Shipment ID": s.shipment_id,
            "From": system.locations[s.source_id].name,
            "To": system.locations[s.destination_id].name,
            "Status": s.status.value,
            "Vehicle": s.vehicle_id or "Not Assigned",
            "Requested At": s.requested_at.strftime("%Y-%m-%d %H:%M"),
        })

    st.dataframe(pd.DataFrame(data), use_container_width=True)

elif menu == "Locations":
    st.subheader("Add Location")

    with st.form("add_location"):
        name = st.text_input("Location Name")
        location_type = st.selectbox("Type", ["Warehouse", "Office", "Site"])
        address = st.text_area("Address")
        submit = st.form_submit_button("Add Location")

    if submit:
        system.add_location(name, location_type, address)
        st.success("Location added.")

    st.subheader("All Locations")
    st.dataframe(pd.DataFrame([
        {
            "ID": loc.location_id,
            "Name": loc.name,
            "Type": loc.location_type,
            "Address": loc.address,
        }
        for loc in system.locations.values()
    ]), use_container_width=True)

elif menu == "Items":
    st.subheader("Add Item")

    with st.form("add_item"):
        name = st.text_input("Item Name")
        unit = st.text_input("Unit", placeholder="bags, pcs, kg, boxes")
        submit = st.form_submit_button("Add Item")

    if submit:
        system.add_item(name, unit)
        st.success("Item added.")

    st.subheader("All Items")
    st.dataframe(pd.DataFrame([
        {
            "ID": item.item_id,
            "Name": item.name,
            "Unit": item.unit,
        }
        for item in system.items.values()
    ]), use_container_width=True)

elif menu == "Vehicles":
    st.subheader("Add Vehicle")

    with st.form("add_vehicle"):
        plate = st.text_input("Plate Number")
        capacity = st.number_input("Capacity KG", min_value=1.0)
        submit = st.form_submit_button("Add Vehicle")

    if submit:
        system.add_vehicle(plate, capacity)
        st.success("Vehicle added.")

    st.subheader("All Vehicles")
    st.dataframe(pd.DataFrame([
        {
            "ID": v.vehicle_id,
            "Plate": v.plate_number,
            "Capacity KG": v.capacity_kg,
            "Status": "Available" if v.available else "In Use",
        }
        for v in system.vehicles.values()
    ]), use_container_width=True)

elif menu == "Inventory":
    st.subheader("Add Stock")

    loc_map = location_options(system)
    item_map = item_options(system)

    with st.form("add_stock"):
        location_name = st.selectbox("Location", list(loc_map.keys()))
        item_name = st.selectbox("Item", list(item_map.keys()))
        quantity = st.number_input("Quantity", min_value=0.0)
        submit = st.form_submit_button("Add Stock")

    if submit:
        system.add_stock(loc_map[location_name], item_map[item_name], quantity)
        st.success("Stock added.")

    st.subheader("Inventory View")

    rows = []
    for loc_id, stock in system.inventory.items():
        for item_id, qty in stock.items():
            rows.append({
                "Location": system.locations[loc_id].name,
                "Item": system.items[item_id].name,
                "Quantity": qty,
                "Unit": system.items[item_id].unit,
            })

    st.dataframe(pd.DataFrame(rows), use_container_width=True)

elif menu == "Create Shipment":
    st.subheader("Create Shipment")

    loc_map = location_options(system)
    item_map = item_options(system)

    source = st.selectbox("Source", list(loc_map.keys()))
    destination = st.selectbox("Destination", list(loc_map.keys()))
    notes = st.text_area("Notes")

    st.markdown("### Shipment Items")

    selected_items = []

    for i in range(1, 4):
        with st.expander(f"Item {i}", expanded=i == 1):
            item_name = st.selectbox(f"Select Item {i}", list(item_map.keys()), key=f"ship_item_{i}")
            quantity = st.number_input(f"Quantity {i}", min_value=0.0, key=f"ship_qty_{i}")
            weight = st.number_input(f"Weight KG {i}", min_value=0.0, key=f"ship_weight_{i}")

            if quantity > 0:
                selected_items.append(
                    ShipmentItem(
                        item_id=item_map[item_name],
                        quantity=quantity,
                        weight_kg=weight,
                    )
                )

    if st.button("Create Shipment"):
        try:
            shipment_id = system.create_shipment(
                loc_map[source],
                loc_map[destination],
                selected_items,
                notes,
            )
            st.success(f"Shipment created: {shipment_id}")
        except Exception as e:
            st.error(str(e))

elif menu == "Manage Shipments":
    st.subheader("Manage Shipments")

    ship_map = shipment_options(system)

    if not ship_map:
        st.info("No shipments available.")
    else:
        selected = st.selectbox("Select Shipment", list(ship_map.keys()))
        shipment_id = ship_map[selected]
        shipment = system.shipments[shipment_id]

        st.write(f"**Status:** {shipment.status.value}")
        st.write(f"**From:** {system.locations[shipment.source_id].name}")
        st.write(f"**To:** {system.locations[shipment.destination_id].name}")
        st.write(f"**Vehicle:** {shipment.vehicle_id or 'Not Assigned'}")
        st.write(f"**Notes:** {shipment.notes}")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if st.button("Approve"):
                try:
                    system.approve_shipment(shipment_id)
                    st.success("Shipment approved.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

        with col2:
            if st.button("Assign Vehicle"):
                try:
                    vehicle_id = system.assign_vehicle(shipment_id)
                    st.success(f"Vehicle assigned: {vehicle_id}")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

        with col3:
            if st.button("Dispatch"):
                try:
                    system.dispatch_shipment(shipment_id)
                    st.success("Shipment dispatched.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

        with col4:
            if st.button("Deliver"):
                try:
                    system.deliver_shipment(shipment_id)
                    st.success("Shipment delivered.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

        if st.button("Cancel Shipment"):
            try:
                system.cancel_shipment(shipment_id)
                st.warning("Shipment cancelled.")
                st.rerun()
            except Exception as e:
                st.error(str(e))

elif menu == "Reports":
    st.subheader("Shipment Report")

    rows = []

    for s in system.shipments.values():
        rows.append({
            "Shipment ID": s.shipment_id,
            "Source": system.locations[s.source_id].name,
            "Destination": system.locations[s.destination_id].name,
            "Status": s.status.value,
            "Vehicle": s.vehicle_id or "Not Assigned",
            "Requested": s.requested_at.strftime("%Y-%m-%d %H:%M"),
            "Approved": s.approved_at.strftime("%Y-%m-%d %H:%M") if s.approved_at else "",
            "Dispatched": s.dispatched_at.strftime("%Y-%m-%d %H:%M") if s.dispatched_at else "",
            "Delivered": s.delivered_at.strftime("%Y-%m-%d %H:%M") if s.delivered_at else "",
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)

    if not df.empty:
        st.download_button(
            "Download Shipment Report CSV",
            df.to_csv(index=False),
            "shipment_report.csv",
            "text/csv",
        )