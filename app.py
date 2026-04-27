import streamlit as st
import pandas as pd
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
import uuid
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
import tempfile
import os




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
def generate_delivery_challan_pdf(
    challan_no,
    challan_date,
    dispatch_date,
    order_date,
    ref_no,
    company_name,
    company_address,
    consignee_name,
    consignee_address,
    place_of_supply,
    gstin,
    phone,
    challan_type,
    notes,
    items,
    dc_type,
    logo_path="assets/logo.png",
):
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf_path = temp_file.name
    temp_file.close()

    c = canvas.Canvas(pdf_path, pagesize=A4)
    width, height = A4

    c.rect(12 * mm, 12 * mm, width - 24 * mm, height - 24 * mm)

    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, height - 25 * mm, "DELIVERY CHALLAN")

    c.setFont("Helvetica-Bold", 9)
    c.drawString(18 * mm, height - 38 * mm, f"Delivery Challan# - {challan_no}")

    c.setFont("Helvetica-Bold", 9)
    c.drawString(18 * mm, height - 50 * mm, company_name)

    c.setFont("Helvetica", 8)
    y = height - 56 * mm
    for line in company_address.split("\n"):
        c.drawString(18 * mm, y, line)
        y -= 4 * mm

    y -= 2 * mm
    c.drawString(18 * mm, y, f"GSTIN: {gstin}")
    y -= 4 * mm
    c.drawString(18 * mm, y, f"Phone: {phone}")

    x = 125 * mm
    y = height - 50 * mm

    details = [
        ("Delivery Challan #", challan_no),
        ("Challan Date #", challan_date),
        ("Dispatch Date #", dispatch_date),
        ("Order Date #", order_date),
        ("Ref #", ref_no),
        ("Place of Supply", place_of_supply),
        ("Challan Type", challan_type),
    ]

    for label, value in details:
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x, y, label)
        c.setFont("Helvetica", 8)
        c.drawString(x + 35 * mm, y, str(value))
        y -= 5 * mm

    y = height - 105 * mm
    c.setFont("Helvetica-Bold", 9)

    if dc_type == "OUTWARD":
        c.drawString(18 * mm, y, "OUTWARD")
        y -= 6 * mm
        c.drawString(18 * mm, y, "Company Address:")
        y -= 5 * mm

        c.setFont("Helvetica-Bold", 8)
        c.drawString(18 * mm, y, company_name)
        y -= 5 * mm

        c.setFont("Helvetica", 8)
        for line in company_address.split("\n"):
            c.drawString(18 * mm, y, line)
            y -= 4 * mm

    else:
        c.drawString(18 * mm, y, "INWARD")
        y -= 6 * mm
        c.drawString(18 * mm, y, "Consignee:")
        y -= 5 * mm

        c.setFont("Helvetica-Bold", 8)
        c.drawString(18 * mm, y, consignee_name)
        y -= 5 * mm

        c.setFont("Helvetica", 8)
        for line in consignee_address.split("\n"):
            c.drawString(18 * mm, y, line)
            y -= 4 * mm

    y -= 5 * mm
    c.setFont("Helvetica-Bold", 8)
    c.drawString(18 * mm, y, "Notes:")
    c.setFont("Helvetica", 8)
    c.drawString(35 * mm, y, notes)

    table_y = height - 150 * mm

    c.setFont("Helvetica-Bold", 9)
    c.rect(18 * mm, table_y, 174 * mm, 10 * mm)
    c.drawString(22 * mm, table_y + 3 * mm, "SR No.")
    c.drawString(45 * mm, table_y + 3 * mm, "ITEM DESCRIPTION")
    c.drawString(170 * mm, table_y + 3 * mm, "QTY")

    row_y = table_y - 10 * mm
    c.setFont("Helvetica", 9)

    for index, item in enumerate(items, start=1):
        c.rect(18 * mm, row_y, 174 * mm, 10 * mm)
        c.drawString(22 * mm, row_y + 3 * mm, str(index))
        c.drawString(45 * mm, row_y + 3 * mm, item["description"])
        c.drawString(172 * mm, row_y + 3 * mm, str(item["qty"]))
        row_y -= 10 * mm

    c.setFont("Helvetica-Bold", 8)
    c.drawString(18 * mm, 22 * mm, dc_type)
    c.drawRightString(width - 18 * mm, 22 * mm, "Page 1")

    if logo_path and os.path.exists(logo_path):
        c.drawImage(
            logo_path,
            140 * mm,
            28 * mm,
            width=40 * mm,
            height=25 * mm,
            preserveAspectRatio=True,
            mask="auto",
        )

    c.save()
    return pdf_path


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
    "Generate Delivery Challan",
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
                
                
elif menu == "Generate Delivery Challan":
    st.subheader("Generate Delivery Challan")

    with st.form("dc_form"):
        dc_type = st.selectbox("DC Type", ["OUTWARD", "INWARD"])

        col1, col2 = st.columns(2)

        with col1:
            challan_no = st.text_input("Delivery Challan #", "APH-62")
            challan_date = st.date_input("Challan Date")
            dispatch_date = st.date_input("Dispatch Date")
            order_date = st.date_input("Order Date")
            ref_no = st.text_input("Ref #", "PMW_374909")
            place_of_supply = st.text_input("Place of Supply", "Karnataka")

        with col2:
            gstin = st.text_input("GSTIN", "29ATFPP7294R1ZF")
            phone = st.text_input("Phone", "+91 8951975583")
            challan_type = st.text_input("Challan Type", "Material/Accessories")
            notes = st.text_input("Notes", "FOR REPAIRING")

        st.markdown("### Default Company Details")

        company_name = st.text_input(
            "Company Name",
            "ZOBOCON ENGINEERING PVT LTD",
        )

        company_address = st.text_area(
            "Company Address",
            "25, 2nd Floor, Karna Sree Point, Opposite Kalamandir Outer Ring Road,\n"
            "Service Rd, Marathahalli, Bengaluru, Karnataka 560037",
        )

        if dc_type == "INWARD":
            st.markdown("### Consignee Details")

            consignee_name = st.text_input(
                "Consignee Name",
                "Enter Consignee Name",
            )

            consignee_address = st.text_area(
                "Consignee Address",
                "Enter Consignee Address",
            )
        else:
            consignee_name = company_name
            consignee_address = company_address

        st.markdown("### Items")

        items = []

        for i in range(1, 8):
            col_a, col_b = st.columns([4, 1])

            with col_a:
                description = st.text_input(
                    f"Item Description {i}",
                    "Bison Plus Wall Putty (Pac-40kg)" if i == 1 else "",
                    key=f"dc_item_desc_{i}",
                )

            with col_b:
                qty = st.number_input(
                    f"Qty {i}",
                    min_value=0,
                    value=15 if i == 1 else 0,
                    key=f"dc_qty_{i}",
                )

            if description and qty > 0:
                items.append(
                    {
                        "description": description,
                        "qty": qty,
                    }
                )

        submit = st.form_submit_button("Generate DC PDF")

    if submit:
        if not items:
            st.error("Please add at least one item.")
        else:
            pdf_path = generate_delivery_challan_pdf(
                challan_no=challan_no,
                challan_date=challan_date.strftime("%d-%b-%y"),
                dispatch_date=dispatch_date.strftime("%d-%b-%y"),
                order_date=order_date.strftime("%d-%b-%y"),
                ref_no=ref_no,
                company_name=company_name,
                company_address=company_address,
                consignee_name=consignee_name,
                consignee_address=consignee_address,
                place_of_supply=place_of_supply,
                gstin=gstin,
                phone=phone,
                challan_type=challan_type,
                notes=notes,
                items=items,
                dc_type=dc_type,
                logo_path="assets/logo.png",
            )

            with open(pdf_path, "rb") as file:
                st.success("Delivery Challan generated.")
                st.download_button(
                    label="Download Delivery Challan PDF",
                    data=file,
                    file_name=f"Delivery_Challan_{dc_type}_{challan_no}.pdf",
                    mime="application/pdf",
                )
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