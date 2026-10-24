import DataSummary from './DataSummary.vue'
import SeineCurves from './SeineCurves.vue'
import BayesBand from './BayesBand.vue'
import PduSummary from './PduSummary.vue'
import PduBreakdown from './PduBreakdown.vue'
import ForecastScenarios from './ForecastScenarios.vue'
import CalcStockView from './CalcStockView.vue'

export default {
  data_summary: DataSummary,
  seine_curves: SeineCurves,
  net_curves: SeineCurves,
  bayes_band: BayesBand,
  pdu_summary: PduSummary,
  pdu_breakdown: PduBreakdown,
  forecast_scenarios: ForecastScenarios,
  calc_likelihood: CalcStockView,
  calc_gear_stock: CalcStockView,
  calc_combined: CalcStockView,
}
