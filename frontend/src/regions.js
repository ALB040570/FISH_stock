// Справочник «Области»: коды → названия на текущем языке
import { dictName, dictNames, loadDict } from './dicts'

export const loadRegions = () => loadDict('regions')
export const regionName = (code) => dictName('regions', code)
export const regionNames = (codes) => dictNames('regions', codes)
