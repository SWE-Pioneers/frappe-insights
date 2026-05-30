<script setup lang="ts">
import { Combobox, MultiSelect, debounce } from 'frappe-ui'
import { computed, onMounted, ref } from 'vue'
import { flattenOptions } from '../../helpers'
import {
	ColumnOption,
	FilterOperator,
	FilterRule,
	GroupedColumnOption,
} from '../../types/query.types'
import { column } from '../helpers'
import useQuery from '../query'
import DatePickerControl from './DatePickerControl.vue'
import { getFilterType, getOperatorOptions, getValueSelectorType } from './filter_utils'
import RelativeDatePickerControl from './RelativeDatePickerControl.vue'

const filter = defineModel<FilterRule>({ required: true })
const props = defineProps<{
	columnOptions: ColumnOption[] | GroupedColumnOption[]
}>()
const availableColumnOptions = computed(() => flattenOptions(props.columnOptions) as ColumnOption[])

onMounted(() => {
	if (valueSelectorType.value === 'select') fetchColumnValues()
})

function onColumnChange(column_name: string) {
	filter.value.column = column(column_name)
	filter.value.operator = operatorOptions.value[0]?.value
	filter.value.value = undefined
	if (valueSelectorType.value === 'select') {
		filter.value.value = []
		fetchColumnValues()
	}
}

const columnType = computed(() => {
	if (!props.columnOptions?.length) return
	if (!filter.value.column.column_name) return
	const col = availableColumnOptions.value.find(
		(c) => c.value === filter.value.column.column_name,
	)
	if (!col) throw new Error(`Column not found: ${filter.value.column.column_name}`)
	return col.data_type
})

const operatorOptions = computed(() => {
	if (!columnType.value) return []
	return getOperatorOptions(getFilterType(columnType.value))
})

function onOperatorChange(operator: FilterOperator) {
	filter.value.operator = operator
	filter.value.value = undefined
}

function updateSelectedColumn(value: string | null) {
	onColumnChange(value ?? '')
}

const valueSelectorType = computed(() => {
	if (!filter.value.column.column_name || !filter.value.operator || !columnType.value) {
		return
	}
	return getValueSelectorType(filter.value.operator, getFilterType(columnType.value))
})

const distinctColumnValues = ref<string[]>([])
const fetchingValues = ref(false)
const selectedFilterValues = computed(() => {
	return Array.isArray(filter.value.value)
		? filter.value.value.filter((value): value is string => typeof value === 'string')
		: []
})
const distinctValueOptions = computed(() => {
	return [...new Set([...selectedFilterValues.value, ...distinctColumnValues.value])].map(
		(value) => ({
			label: value,
			value,
		}),
	)
})

function updateSelectedValues(value: unknown) {
	filter.value.value = Array.isArray(value)
		? value.filter((item): item is string => typeof item === 'string')
		: []
}

const fetchColumnValues = debounce((searchTxt: string) => {
	const option = availableColumnOptions.value.find(
		(c) => c.value === filter.value.column.column_name,
	)
	if (!option?.query) {
		fetchingValues.value = false
		console.warn('Query not found for column:', filter.value.column.column_name)
		return
	}
	// only for dashboard filters
	// if column_name is {sep}query{sep}.{sep}column_name{sep} extract column_name
	const sep = '`'
	const pattern = new RegExp(`${sep}([^${sep}]+)${sep}\\.${sep}([^${sep}]+)${sep}`)
	const match = pattern.exec(filter.value.column.column_name)
	const column_name = match ? match[2] : filter.value.column.column_name

	fetchingValues.value = true
	return useQuery(option.query)
		.getDistinctColumnValues(column_name, searchTxt)
		.then((values: string[]) => (distinctColumnValues.value = values))
		.finally(() => (fetchingValues.value = false))
}, 300)
</script>

<template>
	<div class="flex flex-1 gap-2">
		<div id="column_name" class="!min-w-[140px] flex-1 flex-shrink-0">
			<Combobox
				placeholder="Column"
				:modelValue="filter.column.column_name"
				:options="availableColumnOptions"
				@update:modelValue="updateSelectedColumn"
			/>
		</div>
		<div id="operator" class="!min-w-[100px] flex-1">
			<FormControl
				type="select"
				placeholder="Operator"
				:disabled="!columnType"
				:modelValue="filter.operator"
				:options="operatorOptions"
				@update:modelValue="onOperatorChange($event)"
			/>
		</div>
		<div id="value" class="!min-w-[140px] flex-1 flex-shrink-0">
			<FormControl
				v-if="valueSelectorType === 'text'"
				v-model="filter.value"
				placeholder="Value"
				autocomplete="off"
			/>
			<FormControl
				v-else-if="valueSelectorType === 'number'"
				type="number"
				:modelValue="filter.value"
				placeholder="Value"
				@update:modelValue="filter.value = Number($event)"
			/>
			<DatePickerControl
				v-else-if="valueSelectorType === 'date'"
				placeholder="Select Date"
				:modelValue="[filter.value as string]"
				@update:modelValue="filter.value = $event[0]"
			/>
			<DatePickerControl
				v-else-if="valueSelectorType === 'date_range'"
				:range="true"
				v-model="filter.value as string[]"
				placeholder="Select Date"
			/>
			<RelativeDatePickerControl
				v-else-if="valueSelectorType === 'relative_date'"
				v-model="filter.value as string"
				placeholder="Relative Date"
			/>
			<MultiSelect
				v-else-if="valueSelectorType === 'select'"
				class="max-w-[200px]"
				placeholder="Value"
				:modelValue="selectedFilterValues"
				:options="distinctValueOptions"
				:loading="fetchingValues"
				@update:query="fetchColumnValues"
				@update:modelValue="updateSelectedValues"
			/>
			<FormControl v-else disabled />
		</div>
	</div>
</template>
