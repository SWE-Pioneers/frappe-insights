<script setup lang="ts">
import { Combobox } from 'frappe-ui'
import { computed, inject, reactive, ref, watch } from 'vue'
import { UnionArgs } from '../../types/query.types'
import { workbookKey } from '../../workbook/workbook'
import { query_table, table } from '../helpers'
import { Query } from '../query'
import { useTableOptions } from './join_utils'
import { __ } from '../../translation'

const props = defineProps<{ union?: UnionArgs }>()
const emit = defineEmits({
	select: (join: UnionArgs) => true,
})
const showDialog = defineModel()

const union = reactive<UnionArgs>(
	props.union
		? { ...props.union }
		: {
				table: table({}),
				distinct: false,
		  },
)
const selectedTableOption = computed({
	get() {
		if (union.table.type === 'table' && union.table.table_name) {
			return `${union.table.data_source}.${union.table.table_name}`
		}
		if (union.table.type === 'query' && union.table.query_name) {
			return union.table.query_name
		}
	},
	set(value: string) {
		const option = [...queryTableOptions.value, ...tableOptions.options].find(
			(option) => option.value === value,
		)
		if (!option) return
		if (
			'data_source' in option &&
			'table_name' in option &&
			option.data_source &&
			option.table_name
		) {
			union.table = table({
				data_source: option.data_source,
				table_name: option.table_name,
			})
		}
		if ('query_name' in option && option.query_name) {
			union.table = query_table({
				workbook: option.workbook,
				query_name: option.query_name,
			})
		}
	},
})

const query = inject('query') as Query
const data_source = computed(() => query.dataSource)

const rightTable = computed(() => {
	return union.table.type === 'table' ? union.table.table_name : ''
})
const tableOptions = useTableOptions({
	data_source,
	initialSearchText: rightTable.value,
})

const workbook = inject(workbookKey)!
const queryTableOptions = computed(() => {
	const linkedQueries = workbook.getLinkedQueries(query.doc.name)
	return workbook.doc.queries
		.filter((q) => q.name !== query.doc.name && !linkedQueries.includes(q.name))
		.map((q) => {
			return {
				workbook: workbook.doc.name,
				query_name: q.name,
				label: q.title,
				value: q.name,
				description: __('Query'),
			}
		})
})

const groupedTableOptions = computed(() => {
	return [
		{
			group: 'Queries',
			options: queryTableOptions.value,
		},
		{
			group: 'Tables',
			options: tableOptions.options,
		},
	]
})

function getUnionState() {
	return JSON.stringify({
		table: union.table,
		distinct: union.distinct,
	})
}

const initialUnionState = ref('')
watch(
	showDialog,
	(open) => {
		if (open) {
			initialUnionState.value = getUnionState()
		}
	},
	{ immediate: true },
)

const isDirty = computed(
	() => !!initialUnionState.value && getUnionState() !== initialUnionState.value,
)

const isValid = computed(() => {
	return (
		(union.table.type === 'table' && union.table.table_name) ||
		(union.table.type === 'query' && union.table.query_name)
	)
})
function confirm() {
	if (!isValid.value) return
	emit('select', { ...union })
	showDialog.value = false
	reset()
}
function reset() {
	Object.assign(union, {
		table: table({}),
		distinct: false,
	})
}
</script>

<template>
	<Dialog v-model:open="showDialog" :title="__('Append Rows')" :dismissible="!isDirty">
		<div class="text-base">
			<!-- Fields -->
			<div class="flex w-full flex-col gap-3 overflow-auto p-0.5">
				<div>
					<label class="mb-1 block text-xs text-gray-600">{{ __('Select Table') }}</label>
					<Combobox
						:placeholder="__('Table')"
						v-model="selectedTableOption"
						:loading="tableOptions.loading"
						:options="groupedTableOptions"
						@input="tableOptions.searchText = $event"
					/>
				</div>
				<div>
					<FormControl
						type="select"
						:label="__('Drop Duplicates')"
						:modelValue="union.distinct ? 'true' : 'false'"
						@update:modelValue="union.distinct = $event === 'true'"
						:options="[
							{ label: __('Yes'), value: 'true' },
							{ label: __('No'), value: 'false' },
						]"
					/>
				</div>
			</div>

			<!-- Actions -->
			<div class="mt-4 flex justify-end gap-2">
				<Button variant="outline" :label="__('Cancel')" @click="showDialog = false" />
				<Button
					variant="solid"
					:label="__('Confirm')"
					:disabled="!isValid"
					@click="confirm"
				/>
			</div>
		</div>
	</Dialog>
</template>
