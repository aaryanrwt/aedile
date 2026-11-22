def ai_flight_hook(state, dt):
    if state.boosting and state.hover_z > 0.25:
        state.score += dt * 60.0 * state.combo
    if state.hover_z == 0.0 and not state.boosting:
        state.battery = min(state.battery + 4.0 * dt, 100.0)
