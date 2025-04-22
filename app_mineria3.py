import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import copy

# --- Configuración de Página ---
st.set_page_config(layout="wide", page_title="Simulador Minero Detallado+")

# --- Inicializar Session State ---
default_states = {
    'mining_scenarios_detailed': [],
    'run_counter_detailed': 0,
    # Targets
    'tonnes_mined_target': 120000,
    'strip_ratio': 3.0,
    'plant_feed_target': 100000,
    # --- NUEVO: Voladura ---
    'tonnes_blasted_period': 480000, # Ejemplo: (Ore + Waste) = 120k * (1+3)
    'load_factor_kg_t': 0.35, # kg de explosivo por tonelada volada
    'explosive_cost_usd_kg': 1.20, # $/kg de explosivo
    # Flota
    'truck_count': 10, 'truck_op_hours_period': 6000, 'truck_payload': 100, 'avg_cycle_time_min': 30.0,
    'loader_count': 3, 'loader_op_hours_period': 1800, 'loader_rate_tph': 500,
    # Planta
    'plant_op_hours_period': 650, 'plant_throughput_tph': 160,
    # Metalurgia y Mercado
    'grade_pct': 1.0, 'recovery_pct': 85.0, 'metal_price': 3.50, 'exchange_rate': 1.0,
    # Costos Unitarios y Fijos
    # --- AJUSTADO: Costo P&V ahora es solo Perforación y Accesorios ---
    'cost_drill_acc_per_t_blasted': 0.80, # $/tonelada VOLADA (sin explosivo)
    'cost_load_per_hr': 250.0, 'cost_haul_per_hr': 300.0, 'cost_process_per_hr': 5000.0,
    'cost_maint_fixed': 200000.0, 'cost_ga_fixed': 300000.0,
}
for key, default_value in default_states.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

# --- Título y Descripción ---
st.title("⛏️ Simulador Minero Detallado+ (v4.2 - Voladura)")
st.markdown("""
Simula resultados financieros y operativos incluyendo costos detallados de **Perforación y Voladura**.
Ajuste parámetros y observe el impacto en costos, KPIs y rentabilidad.
""")

# --- Modelo de Cálculo Detallado (MODIFICADO) ---
def calculate_detailed_metrics(
    # Targets
    tonnes_mined_target, strip_ratio, plant_feed_target,
    # === NUEVO: Voladura ===
    tonnes_blasted_period, load_factor_kg_t, explosive_cost_usd_kg,
    # Flota Carga/Acarreo
    truck_count, truck_op_hours_period, truck_payload, avg_cycle_time_min,
    loader_count, loader_op_hours_period, loader_rate_tph,
    # Planta
    plant_op_hours_period, plant_throughput_tph,
    # Metalurgia y Mercado
    grade_pct, recovery_pct, metal_price, exchange_rate,
    # Costos Unitarios y Fijos
    # === AJUSTADO ===
    cost_drill_acc_per_t_blasted, # Costo Perforación y Accesorios por ton volada
    cost_load_per_hr, cost_haul_per_hr, cost_process_per_hr,
    cost_maint_fixed, cost_ga_fixed):
    """Calcula métricas financieras y operativas desde parámetros detallados."""
    results = {}
    kpis = {}
    errors = []
    warnings = []

    # --- Validaciones Básicas ---
    # ... (validaciones anteriores) ...
    if tonnes_blasted_period <= 0: errors.append("Toneladas Voladas debe ser > 0")
    if load_factor_kg_t <= 0: errors.append("Factor Carga Explosivo debe ser > 0")
    if explosive_cost_usd_kg < 0: errors.append("Costo Explosivo no puede ser negativo")
    if cost_drill_acc_per_t_blasted < 0: errors.append("Costo Perf.&Acc. no puede ser negativo")
    # ... (resto de validaciones) ...
    if tonnes_mined_target <= 0: errors.append("Target Toneladas Minadas debe ser > 0")
    if strip_ratio < 0: errors.append("Strip Ratio no puede ser negativo")
    if plant_feed_target <= 0: errors.append("Target Alimentación Planta debe ser > 0")
    if avg_cycle_time_min <= 0: errors.append("Tiempo Ciclo Camión debe ser > 0")
    #... (añadir más validaciones si es necesario)

    if errors: return None, None, errors, warnings
    try:
        # --- Cálculos de Productividad y Capacidad (sin cambios) ---
        total_loader_hours_avail = loader_count * loader_op_hours_period
        potential_tonnes_loaded = total_loader_hours_avail * loader_rate_tph
        kpis['potential_tonnes_loaded'] = potential_tonnes_loaded; kpis['total_loader_hours_avail'] = total_loader_hours_avail
        total_truck_hours_avail = truck_count * truck_op_hours_period
        trips_per_truck_hour = 60.0 / avg_cycle_time_min
        potential_tonnes_hauled_per_truck_hour = trips_per_truck_hour * truck_payload
        potential_tonnes_hauled = total_truck_hours_avail * potential_tonnes_hauled_per_truck_hour
        kpis['potential_tonnes_hauled'] = potential_tonnes_hauled; kpis['total_truck_hours_avail'] = total_truck_hours_avail; kpis['trips_per_truck_hour'] = trips_per_truck_hour; kpis['potential_tph_per_truck'] = potential_tonnes_hauled_per_truck_hour
        potential_tonnes_processed = plant_op_hours_period * plant_throughput_tph
        kpis['potential_tonnes_processed'] = potential_tonnes_processed; kpis['plant_op_hours_period'] = plant_op_hours_period

        # --- Determinación de Toneladas Reales (sin cambios) ---
        actual_tonnes_mined = tonnes_mined_target
        actual_waste_moved = actual_tonnes_mined * strip_ratio
        actual_total_material_moved = actual_tonnes_mined + actual_waste_moved
        actual_tonnes_processed = plant_feed_target

        # --- Advertencias de Capacidad (sin cambios) ---
        if actual_total_material_moved > potential_tonnes_loaded: warnings.append(f"Movido ({actual_total_material_moved:,.0f}t) > Cap. Carga ({potential_tonnes_loaded:,.0f}t)")
        if actual_total_material_moved > potential_tonnes_hauled: warnings.append(f"Movido ({actual_total_material_moved:,.0f}t) > Cap. Acarreo ({potential_tonnes_hauled:,.0f}t)")
        if actual_tonnes_processed > potential_tonnes_processed: warnings.append(f"Procesado ({actual_tonnes_processed:,.0f}t) > Cap. Proceso ({potential_tonnes_processed:,.0f}t)")
        # Advertencia si las toneladas voladas no coinciden con el material movido target
        # (Puede ser intencional si hay cambios de inventario en cancha)
        if not np.isclose(tonnes_blasted_period, actual_total_material_moved):
             warnings.append(f"Toneladas Voladas ({tonnes_blasted_period:,.0f}t) != Material Movido Target ({actual_total_material_moved:,.0f}t)")


        # === MODIFICADO: Cálculos de Costos por Área ===

        # --- Costo Perforación y Voladura Detallado ---
        # 1. Costo Explosivos
        total_explosive_kg = tonnes_blasted_period * load_factor_kg_t
        cost_explosives_total = total_explosive_kg * explosive_cost_usd_kg
        results['cost_explosives'] = cost_explosives_total
        kpis['total_explosive_kg'] = total_explosive_kg

        # 2. Costo Perforación y Accesorios (basado en ton voladas)
        cost_drill_acc_total = tonnes_blasted_period * cost_drill_acc_per_t_blasted
        results['cost_drill_accessories'] = cost_drill_acc_total

        # 3. Costo Total P&V
        cost_pv_total = cost_explosives_total + cost_drill_acc_total
        results['cost_drill_blast_total'] = cost_pv_total # Renombrado para claridad interna

        # --- Costo Carga, Acarreo, Proceso (sin cambios en la lógica) ---
        required_loader_hours = actual_total_material_moved / (loader_rate_tph * loader_count) if (loader_rate_tph * loader_count) > 0 else float('inf')
        actual_loader_hours_used = min(required_loader_hours, total_loader_hours_avail)
        if required_loader_hours > total_loader_hours_avail: warnings.append("Hr carga req > disp.")
        cost_load_total = actual_loader_hours_used * cost_load_per_hr; results['cost_loading'] = cost_load_total; kpis['actual_loader_hours_used'] = actual_loader_hours_used

        required_truck_hours = actual_total_material_moved / (potential_tonnes_hauled_per_truck_hour * truck_count) if (potential_tonnes_hauled_per_truck_hour * truck_count) > 0 else float('inf')
        actual_truck_hours_used = min(required_truck_hours, total_truck_hours_avail)
        if required_truck_hours > total_truck_hours_avail: warnings.append("Hr acarreo req > disp.")
        cost_haul_total = actual_truck_hours_used * cost_haul_per_hr; results['cost_hauling'] = cost_haul_total; kpis['actual_truck_hours_used'] = actual_truck_hours_used

        required_plant_hours = actual_tonnes_processed / plant_throughput_tph if plant_throughput_tph > 0 else float('inf')
        actual_plant_hours_used = min(required_plant_hours, plant_op_hours_period)
        if required_plant_hours > plant_op_hours_period: warnings.append("Hr planta req > disp.")
        cost_process_total = actual_plant_hours_used * cost_process_per_hr; results['cost_processing'] = cost_process_total; kpis['actual_plant_hours_used'] = actual_plant_hours_used

        # --- Costos Fijos (sin cambios) ---
        results['cost_maintenance_fixed'] = cost_maint_fixed
        results['cost_ga_fixed'] = cost_ga_fixed

        # --- Costo Total y Unitarios (usando nuevo costo P&V) ---
        total_operational_cost = cost_pv_total + cost_load_total + cost_haul_total + cost_process_total # Modificado
        total_cost = total_operational_cost + cost_maint_fixed + cost_ga_fixed
        results['total_operational_cost'] = total_operational_cost
        results['total_cost'] = total_cost
        results['cost_per_tonne_mined'] = total_cost / actual_tonnes_mined if actual_tonnes_mined else 0
        results['cost_per_tonne_processed'] = total_cost / actual_tonnes_processed if actual_tonnes_processed else 0
        kpis['cost_per_total_tonne_moved'] = total_cost / actual_total_material_moved if actual_total_material_moved else 0

        # --- Ingresos y Rentabilidad (sin cambios) ---
        grade_decimal = grade_pct / 100.0; recovery_decimal = recovery_pct / 100.0
        metal_produced_units = actual_tonnes_processed * grade_decimal * recovery_decimal
        revenue = metal_produced_units * metal_price / exchange_rate
        results['revenue'] = revenue; results['metal_produced_units'] = metal_produced_units
        operating_profit = revenue - total_cost
        results['operating_profit'] = operating_profit
        results['profit_per_tonne_processed'] = operating_profit / actual_tonnes_processed if actual_tonnes_processed else 0

        # --- KPIs Operativos Adicionales (sin cambios) ---
        kpis['actual_tonnes_per_truck_hr'] = actual_total_material_moved / actual_truck_hours_used if actual_truck_hours_used > 0 else 0
        kpis['actual_tonnes_per_loader_hr'] = actual_total_material_moved / actual_loader_hours_used if actual_loader_hours_used > 0 else 0
        kpis['actual_tph_plant'] = actual_tonnes_processed / actual_plant_hours_used if actual_plant_hours_used > 0 else 0

        return results, kpis, errors, warnings

    except Exception as e:
        return None, None, [f"Error inesperado en cálculo: {e}"], warnings


# --- Barra Lateral de Inputs (AÑADIR NUEVOS INPUTS) ---
st.sidebar.header("📉 Parámetros del Escenario Detallado")

with st.sidebar.expander("🎯 Targets Operativos", expanded=True):
    tonnes_mined_target = st.number_input("Target Toneladas Minadas (Ore)", min_value=0, value=st.session_state.tonnes_mined_target, step=10000, key="target_t_mined")
    strip_ratio = st.number_input("Strip Ratio (Waste/Ore)", min_value=0.0, value=float(st.session_state.strip_ratio), step=0.1, format="%.1f", key="target_sr")
    plant_feed_target = st.number_input("Target Alimentación Planta (Ore)", min_value=0, value=st.session_state.plant_feed_target, step=10000, key="target_t_plant")
    st.session_state.tonnes_mined_target = tonnes_mined_target; st.session_state.strip_ratio = strip_ratio; st.session_state.plant_feed_target = plant_feed_target

# === NUEVO EXPANDER PARA VOLADURA ===
with st.sidebar.expander("💥 Perforación y Voladura"):
    tonnes_blasted_period = st.number_input("Toneladas Totales Voladas / Periodo", min_value=0, value=st.session_state.tonnes_blasted_period, step=10000, key="blast_tonnes")
    load_factor_kg_t = st.number_input("Factor Carga Explosivo (kg/t volada)", min_value=0.0, value=float(st.session_state.load_factor_kg_t), step=0.01, format="%.2f", key="blast_factor")
    explosive_cost_usd_kg = st.number_input("Costo Explosivo ($/kg)", min_value=0.0, value=float(st.session_state.explosive_cost_usd_kg), step=0.05, format="%.2f", key="blast_cost_kg")
    # Costo de Perforación y Accesorios ( $/t VOLADA )
    cost_drill_acc_per_t_blasted = st.number_input("Costo Perf. & Acc. ($/t volada)", min_value=0.0, value=float(st.session_state.cost_drill_acc_per_t_blasted), step=0.05, format="%.2f", key="cost_drill_acc")
    # Guardar estado
    st.session_state.tonnes_blasted_period=tonnes_blasted_period; st.session_state.load_factor_kg_t=load_factor_kg_t;
    st.session_state.explosive_cost_usd_kg=explosive_cost_usd_kg; st.session_state.cost_drill_acc_per_t_blasted=cost_drill_acc_per_t_blasted;
# === FIN NUEVO ===

with st.sidebar.expander("🚚 Flota Carga y Acarreo"):
    # (Inputs flota - sin cambios, ya corregidos)
    truck_count = st.number_input("N° Camiones Operativos", min_value=1, value=st.session_state.truck_count, step=1, key="fleet_truck_n")
    truck_op_hours_period = st.number_input("Horas Op. Totales Flota / Periodo", min_value=0, value=st.session_state.truck_op_hours_period, step=100, key="fleet_truck_hrs")
    truck_payload = st.number_input("Carga Útil Camión (t)", min_value=1, value=st.session_state.truck_payload, step=5, key="fleet_truck_payload")
    avg_cycle_time_min = st.number_input("Tiempo Ciclo Prom. Camión (min)", min_value=1.0, value=float(st.session_state.avg_cycle_time_min), step=0.5, format="%.1f", key="fleet_truck_cycle")
    loader_count = st.number_input("N° Cargadores Operativos", min_value=1, value=st.session_state.loader_count, step=1, key="fleet_loader_n")
    loader_op_hours_period = st.number_input("Horas Op. Totales Loaders / Periodo", min_value=0, value=st.session_state.loader_op_hours_period, step=50, key="fleet_loader_hrs")
    loader_rate_tph = st.number_input("Tasa Carga (t/hr por Loader)", min_value=1, value=st.session_state.loader_rate_tph, step=10, key="fleet_loader_rate")
    st.session_state.truck_count = truck_count; st.session_state.truck_op_hours_period=truck_op_hours_period; st.session_state.truck_payload=truck_payload; st.session_state.avg_cycle_time_min=avg_cycle_time_min; st.session_state.loader_count=loader_count; st.session_state.loader_op_hours_period=loader_op_hours_period; st.session_state.loader_rate_tph=loader_rate_tph;

with st.sidebar.expander("🏭 Planta de Procesos"):
    # (Inputs planta - sin cambios)
    plant_op_hours_period = st.number_input("Horas Op. Planta / Periodo", min_value=0, value=st.session_state.plant_op_hours_period, step=10, key="plant_hrs")
    plant_throughput_tph = st.number_input("Throughput Prom. (t/hr)", min_value=1, value=st.session_state.plant_throughput_tph, step=5, key="plant_tph")
    st.session_state.plant_op_hours_period=plant_op_hours_period; st.session_state.plant_throughput_tph=plant_throughput_tph;

with st.sidebar.expander("💎 Metalurgia y Mercado"):
    # (Inputs metalurgia/mercado - sin cambios)
    grade_pct = st.slider("Ley de Cabeza (%)", min_value=0.0, max_value=10.0, value=st.session_state.grade_pct, step=0.01, format="%.2f %%", key="metal_grade")
    recovery_pct = st.slider("Recuperación Metalúrgica (%)", min_value=0.0, max_value=100.0, value=st.session_state.recovery_pct, step=0.1, format="%.1f %%", key="metal_rec")
    metal_price = st.number_input("Precio del Metal ($/unidad)", min_value=0.0, value=float(st.session_state.metal_price), step=0.05, format="%.2f", key="metal_price_in")
    exchange_rate = st.number_input("Tipo de Cambio (MonedaLocal/USD)", min_value=0.01, value=float(st.session_state.exchange_rate), step=0.01, format="%.2f", key="fx_rate_in")
    st.session_state.grade_pct=grade_pct; st.session_state.recovery_pct=recovery_pct; st.session_state.metal_price=metal_price; st.session_state.exchange_rate=exchange_rate;

with st.sidebar.expander("💰 Costos Unitarios y Fijos"):
    # (Inputs costos - se quitó P&V global, se añadió Perf&Acc)
    cost_load_per_hr = st.number_input("Costo Carga ($/hr Loader)", min_value=0.0, value=float(st.session_state.cost_load_per_hr), step=5.0, format="%.2f", key="cost_load")
    cost_haul_per_hr = st.number_input("Costo Acarreo ($/hr Camión)", min_value=0.0, value=float(st.session_state.cost_haul_per_hr), step=5.0, format="%.2f", key="cost_haul")
    cost_process_per_hr = st.number_input("Costo Proceso ($/hr Planta)", min_value=0.0, value=float(st.session_state.cost_process_per_hr), step=100.0, format="%.2f", key="cost_proc")
    cost_maint_fixed = st.number_input("Costo Mantención Fija ($/Periodo)", min_value=0.0, value=float(st.session_state.cost_maint_fixed), step=10000.0, format="%.0f", key="cost_maint")
    cost_ga_fixed = st.number_input("Costo G&A Fijo ($/Periodo)", min_value=0.0, value=float(st.session_state.cost_ga_fixed), step=10000.0, format="%.0f", key="cost_ga_f")
    # Guardar estado
    st.session_state.cost_load_per_hr=cost_load_per_hr; st.session_state.cost_haul_per_hr=cost_haul_per_hr; st.session_state.cost_process_per_hr=cost_process_per_hr; st.session_state.cost_maint_fixed=cost_maint_fixed; st.session_state.cost_ga_fixed=cost_ga_fixed;

# --- Ejecutar Cálculo ---
results, kpis, errors, warnings = calculate_detailed_metrics(
    tonnes_mined_target, strip_ratio, plant_feed_target,
    # --- Pasar nuevos inputs ---
    tonnes_blasted_period, load_factor_kg_t, explosive_cost_usd_kg,
    truck_count, truck_op_hours_period, truck_payload, avg_cycle_time_min,
    loader_count, loader_op_hours_period, loader_rate_tph,
    plant_op_hours_period, plant_throughput_tph,
    grade_pct, recovery_pct, metal_price, exchange_rate,
    # --- Pasar costo Perf&Acc ---
    cost_drill_acc_per_t_blasted,
    cost_load_per_hr, cost_haul_per_hr, cost_process_per_hr,
    cost_maint_fixed, cost_ga_fixed
)

# --- Mostrar Resultados y KPIs ---
st.markdown("---")
st.subheader("📊 Resultados del Escenario Actual")
# (Manejo de errores y warnings - sin cambios)
if errors:
    for error in errors: st.error(error)
elif results and kpis: # Solo mostrar si no hubo errores fatales
    if warnings:
        with st.expander("⚠️ Advertencias de Capacidad/Operación"):
            for warning in warnings: st.warning(warning)
    # (Métricas financieras - sin cambios)
    st.markdown("#### Resultados Financieros:")
    col1, col2, col3 = st.columns(3); col1.metric("Ingresos Totales", f"$ {results.get('revenue', 0):,.0f}"); col2.metric("Costo Total", f"$ {results.get('total_cost', 0):,.0f}"); col3.metric("Margen Operativo", f"$ {results.get('operating_profit', 0):,.0f}")
    col4, col5, col6 = st.columns(3); col4.metric("Costo / t Procesada", f"$ {results.get('cost_per_tonne_processed', 0):,.2f}"); col5.metric("Margen / t Procesada", f"$ {results.get('profit_per_tonne_processed', 0):,.2f}"); col6.metric("Metal Vendido (unidades)", f"{results.get('metal_produced_units', 0):,.1f}")

    # (KPIs operativos - sin cambios)
    st.markdown("#### KPIs Operativos Clave:")
    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4); kpi_col1.metric("Ton Movidas / hr-camión*", f"{kpis.get('actual_tonnes_per_truck_hr', 0):,.1f} t/hr"); kpi_col2.metric("Ton Movidas / hr-loader*", f"{kpis.get('actual_tonnes_per_loader_hr', 0):,.1f} t/hr"); kpi_col3.metric("Throughput Real Planta*", f"{kpis.get('actual_tph_plant', 0):,.1f} t/hr"); kpi_col4.metric("Costo / t Movida Total*", f"$ {kpis.get('cost_per_total_tonne_moved', 0):,.2f}"); st.caption("* Calculado basado en horas y toneladas efectivas del periodo simulado.")

    # --- Visualizaciones (MODIFICADO PIE CHART) ---
    st.markdown("---")
    vcol1, vcol2 = st.columns(2)
    with vcol1:
        st.subheader("Desglose Costos Operacionales")
        # === MODIFICADO: Incluir desglose P&V ===
        cost_op_data = {
            'Componente': ['Perf. & Acc.', 'Explosivos', 'Carga', 'Acarreo', 'Procesamiento'],
            'Valor': [results.get('cost_drill_accessories', 0), results.get('cost_explosives', 0),
                      results.get('cost_loading', 0), results.get('cost_hauling', 0),
                      results.get('cost_processing', 0)]
        }
        # === FIN MODIFICADO ===
        df_op_costs = pd.DataFrame(cost_op_data).query("Valor > 0")
        if not df_op_costs.empty:
            fig_op_costs = px.pie(df_op_costs, values='Valor', names='Componente', title='Costos Operacionales Variables', hole=0.3)
            fig_op_costs.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_op_costs, use_container_width=True)

    with vcol2:
        # (Cascada de rentabilidad - sin cambios)
        st.subheader("Cascada de Rentabilidad")
        waterfall_data = {'Concepto': ['Ingresos', 'Costo Operacional', 'Costos Fijos (M&GA)', 'Margen Operativo'], 'Valor': [results.get('revenue', 0), -abs(results.get('total_operational_cost', 0)), -abs(results.get('cost_maintenance_fixed', 0) + results.get('cost_ga_fixed', 0)), results.get('operating_profit', 0)] }
        df_waterfall = pd.DataFrame(waterfall_data); fig_waterfall = go.Figure(go.Waterfall(name="Rentabilidad", orientation="v", measure=["absolute", "relative", "relative", "total"], x=df_waterfall['Concepto'], y=df_waterfall['Valor'], textposition="outside", increasing={"marker": {"color": "green"}}, decreasing={"marker": {"color": "red"}}, totals={"marker": {"color": "blue"}} )); fig_waterfall.update_layout(title="Ingresos -> Margen Operativo", showlegend=False); st.plotly_chart(fig_waterfall, use_container_width=True)

    # --- Guardar Escenario Actual (MODIFICADO PARA NUEVOS INPUTS) ---
    st.markdown("---")
    st.subheader("💾 Guardar y Comparar Escenarios")
    current_run_id_detailed = st.session_state.run_counter_detailed # Usar contador actual
    scenario_name_input = st.text_input("Nombre para este escenario:", f"Escenario Detallado {current_run_id_detailed + 1}", key=f"scn_name_det_{current_run_id_detailed}")

    if st.button("💾 Guardar Escenario Detallado Actual", key=f"save_scn_det_{current_run_id_detailed}"):
        # === MODIFICADO: Capturar todos los inputs nuevos/ajustados ===
        scenario_data = {
            "name": scenario_name_input if scenario_name_input else f"Escenario Detallado {current_run_id_detailed + 1}",
            # Inputs
            "tonnes_mined_target": tonnes_mined_target, "strip_ratio": strip_ratio, "plant_feed_target": plant_feed_target,
            "tonnes_blasted_period": tonnes_blasted_period, "load_factor_kg_t": load_factor_kg_t, "explosive_cost_usd_kg": explosive_cost_usd_kg, # Voladura
            "truck_count": truck_count, "truck_op_hours_period": truck_op_hours_period, "truck_payload": truck_payload, "avg_cycle_time_min": avg_cycle_time_min,
            "loader_count": loader_count, "loader_op_hours_period": loader_op_hours_period, "loader_rate_tph": loader_rate_tph,
            "plant_op_hours_period": plant_op_hours_period, "plant_throughput_tph": plant_throughput_tph,
            "grade_pct": grade_pct, "recovery_pct": recovery_pct, "metal_price": metal_price, "exchange_rate": exchange_rate,
            "cost_drill_acc_per_t_blasted": cost_drill_acc_per_t_blasted, # Ajustado
            "cost_load_per_hr": cost_load_per_hr, "cost_haul_per_hr": cost_haul_per_hr,
            "cost_process_per_hr": cost_process_per_hr, "cost_maint_fixed": cost_maint_fixed, "cost_ga_fixed": cost_ga_fixed,
            # Outputs (Resultados y KPIs)
            "revenue": results.get('revenue'), "total_cost": results.get('total_cost'), "operating_profit": results.get('operating_profit'),
            "cost_per_tonne_processed": results.get('cost_per_tonne_processed'), "profit_per_tonne_processed": results.get('profit_per_tonne_processed'),
            "actual_tonnes_per_truck_hr": kpis.get('actual_tonnes_per_truck_hr'), "actual_tonnes_per_loader_hr": kpis.get('actual_tonnes_per_loader_hr'),
            "actual_tph_plant": kpis.get('actual_tph_plant'), "cost_per_total_tonne_moved": kpis.get('cost_per_total_tonne_moved'),
            "cost_explosives_total": results.get('cost_explosives'), # Guardar costo específico
            "cost_drill_acc_total": results.get('cost_drill_accessories') # Guardar costo específico
        }
        # === FIN MODIFICADO ===
        st.session_state.mining_scenarios_detailed.append(copy.deepcopy(scenario_data))
        st.session_state.run_counter_detailed += 1
        st.success(f"Escenario '{scenario_data['name']}' guardado!")
        # st.experimental_rerun() # Comentado

# --- Sección de Análisis Comparativo (MODIFICADO PARA NUEVOS DATOS) ---
st.markdown("---")
st.subheader("📊 Análisis Comparativo de Escenarios Detallados Guardados")
scenarios_guardados_det = st.session_state.get('mining_scenarios_detailed', [])
if not scenarios_guardados_det:
    st.info("Aún no has guardado ningún escenario detallado.")
else:
    st.write(f"Tienes {len(scenarios_guardados_det)} escenario(s) detallado(s) guardado(s).")
    if st.button("🗑️ Limpiar Escenarios Detallados", key="clear_scenarios_det"):
        st.session_state.mining_scenarios_detailed = []
        st.experimental_rerun()

    # === MODIFICADO: Añadir/Ajustar columnas en comparación ===
    comparison_data_det = []
    for sc in scenarios_guardados_det:
        # Calcular Costo P&V total para mostrar
        pv_cost = sc.get('cost_explosives_total', 0) + sc.get('cost_drill_acc_total', 0)
        ton_blasted = sc.get('tonnes_blasted_period', 0)
        pv_cost_per_ton_blasted = pv_cost / ton_blasted if ton_blasted else 0

        comparison_data_det.append({
            "Escenario": sc.get('name'),
            "Margen Operativo ($)": sc.get('operating_profit'),
            "Costo / t Proc. ($/t)": sc.get('cost_per_tonne_processed'),
            "Costo P&V / t Volada ($/t)": pv_cost_per_ton_blasted, # Nueva Métrica
            "Factor Carga (kg/t)": sc.get('load_factor_kg_t'), # Nuevo Input
            "Ton / hr Camión (t/hr)": sc.get('actual_tonnes_per_truck_hr'),
            "Ton / hr Planta (t/hr)": sc.get('actual_tph_plant'),
            #"Ley (%)": sc.get('grade_pct'), # Opcional quitar algunas para no saturar
            #"Recup (%)": sc.get('recovery_pct'),
            "Precio Metal ($)": sc.get('metal_price'),
        })
    df_comparison_det = pd.DataFrame(comparison_data_det)

    # Ajustar formato
    format_comp = {
        "Margen Operativo ($)": "S/. {:,.0f}",
        "Costo / t Proc. ($/t)": "S/. {:,.2f}",
        "Costo P&V / t Volada ($/t)": "S/. {:,.2f}", # Nuevo Formato
        "Factor Carga (kg/t)": "{:.2f}", # Nuevo Formato
        "Ton / hr Camión (t/hr)": "{:,.1f}",
        "Ton / hr Planta (t/hr)": "{:,.1f}",
        #"Ley (%)": "{:.2f}%",
        #"Recup (%)": "{:.1f}%",
        "Precio Metal ($)": "S/. {:,.2f}"
    }
    st.dataframe(df_comparison_det.style.format(format_comp, na_rep='-'))
    # === FIN MODIFICADO ===

    # Gráficos comparativos (Se puede añadir uno para Costo P&V / t Volada)
    if len(df_comparison_det) > 1:
        # (Gráficos existentes - sin cambios)
        col_comp1, col_comp2 = st.columns(2)
        with col_comp1: fig_comp_profit_det = px.bar(df_comparison_det, x='Escenario', y='Margen Operativo ($)', title='Comparación Margen Operativo', text_auto='.2s'); st.plotly_chart(fig_comp_profit_det, use_container_width=True)
        with col_comp2: fig_comp_cost_det = px.bar(df_comparison_det, x='Escenario', y='Costo / t Proc. ($/t)', title='Comparación Costo / t Procesada', text_auto='.2f'); st.plotly_chart(fig_comp_cost_det, use_container_width=True)

        # --- NUEVO Gráfico Comparativo P&V ---
        col_comp5, col_comp6 = st.columns(2) # Usar nuevos nombres de columna
        with col_comp5:
            fig_comp_pv_cost = px.bar(df_comparison_det, x='Escenario', y='Costo P&V / t Volada ($/t)', title='Comparación Costo P&V / t Volada', text_auto='.2f', labels={'Costo P&V / t Volada ($/t)': 'Costo P&V (S/./t)'})
            st.plotly_chart(fig_comp_pv_cost, use_container_width=True)
        with col_comp6:
             fig_comp_load_factor = px.bar(df_comparison_det, x='Escenario', y='Factor Carga (kg/t)', title='Comparación Factor de Carga', text_auto='.2f', labels={'Factor Carga (kg/t)': 'Factor Carga (kg/t)'})
             st.plotly_chart(fig_comp_load_factor, use_container_width=True)
        # --- FIN NUEVO ---

        # (Gráficos KPI existentes - sin cambios)
        col_comp3, col_comp4 = st.columns(2)
        with col_comp3: fig_comp_truck_kpi = px.bar(df_comparison_det, x='Escenario', y='Ton / hr Camión (t/hr)', title='Comparación Prod. Camiones', text_auto='.1f'); st.plotly_chart(fig_comp_truck_kpi, use_container_width=True)
        with col_comp4: fig_comp_plant_kpi = px.bar(df_comparison_det, x='Escenario', y='Ton / hr Planta (t/hr)', title='Comparación Prod. Planta', text_auto='.1f'); st.plotly_chart(fig_comp_plant_kpi, use_container_width=True)


# --- Notas Finales (Ajustar nota sobre P&V) ---
st.markdown("---")
st.caption("""
*Modelo Detallado Simplificado.* Las relaciones entre equipos, tiempos de ciclo y costos pueden ser más complejas.
**El costo de P&V se calcula sumando el costo de explosivos (basado en ton. voladas y factor de carga) y el costo de perforación/accesorios (basado en $/t volada).**
Ajuste los costos unitarios y factores de conversión de metal a su caso específico.
""")