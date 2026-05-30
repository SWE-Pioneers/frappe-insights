<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { COLUMN_TYPES } from '../../helpers/constants'
import { ColumnDataType, ColumnOption, MutateArgs } from '../../types/query.types'
import { expression } from '../helpers'
import ExpressionEditor from './ExpressionEditor.vue'

const props = defineProps<{ mutation?: MutateArgs; columnOptions: ColumnOption[] }>()
const emit = defineEmits({ select: (column: MutateArgs) => true })
const showDialog = defineModel()

const columnTypes = COLUMN_TYPES.map((t) => t.value as ColumnDataType)

const newColumn = ref(
	props.mutation
		? {
				name: props.mutation.new_name,
				type: props.mutation.data_type,
				expression: props.mutation.expression.expression,
		  }
		: {
				name: 'new_column',
				type: columnTypes[0],
				expression: '',
		  },
)

const isValid = computed(() => {
	return newColumn.value.name && newColumn.value.type && newColumn.value.expression.trim()
})

function getNewColumnState() {
	return JSON.stringify(newColumn.value)
}

const initialNewColumnState = ref('')
watch(
	showDialog,
	(open) => {
		if (open) {
			initialNewColumnState.value = getNewColumnState()
		}
	},
	{ immediate: true },
)

const isDirty = computed(
	() => !!initialNewColumnState.value && getNewColumnState() !== initialNewColumnState.value,
)

function confirmCalculation() {
	if (!isValid.value) return
	emit('select', {
		new_name: newColumn.value.name.trim(),
		data_type: newColumn.value.type,
		expression: expression(newColumn.value.expression),
	})
	resetNewColumn()
	showDialog.value = false
}
function resetNewColumn() {
	newColumn.value = {
		name: 'New Column',
		type: columnTypes[0],
		expression: '',
	}
}
</script>

<template>
	<Dialog
		v-model:open="showDialog"
		size="2xl"
		title="Create Column"
		:dismissible="!isDirty"
		@after-leave="resetNewColumn"
		@close="!newColumn.expression && (showDialog = false)"
	>
		<div>
			<div class="flex flex-col gap-2">
				<ExpressionEditor
					v-model="newColumn.expression"
					:column-options="props.columnOptions"
				/>
				<div class="flex gap-2">
					<FormControl
						type="text"
						class="flex-1"
						label="Column Name"
						autocomplete="off"
						placeholder="Column Name"
						v-model="newColumn.name"
					/>
					<FormControl
						type="select"
						class="flex-1"
						label="Column Type"
						autocomplete="off"
						:options="columnTypes"
						v-model="newColumn.type"
					/>
				</div>
			</div>
			<div class="mt-2 flex items-center justify-between gap-2">
				<div></div>
				<div class="flex items-center gap-2">
					<Button
						label="Confirm"
						variant="solid"
						:disabled="!isValid"
						@click="confirmCalculation"
					/>
				</div>
			</div>
		</div>
	</Dialog>
</template>
