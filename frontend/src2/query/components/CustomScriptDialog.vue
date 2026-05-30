<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ColumnOption, CustomOperationArgs } from '../../types/query.types'
import { expression } from '../helpers'
import ExpressionEditor from './ExpressionEditor.vue'
import { copy } from '../../helpers'

const props = defineProps<{ operation?: CustomOperationArgs; columnOptions: ColumnOption[] }>()
const emit = defineEmits({ select: (operation: CustomOperationArgs) => true })
const showDialog = defineModel()

const newOperation = ref(
	props.operation
		? copy(props.operation)
		: {
				expression: expression(''),
		  },
)

const isValid = computed(() => {
	return newOperation.value.expression.expression.trim().length > 0
})

function getCustomOperationState() {
	return JSON.stringify(newOperation.value)
}

const initialCustomOperationState = ref('')
watch(
	showDialog,
	(open) => {
		if (open) {
			initialCustomOperationState.value = getCustomOperationState()
		}
	},
	{ immediate: true },
)

const isDirty = computed(
	() =>
		!!initialCustomOperationState.value &&
		getCustomOperationState() !== initialCustomOperationState.value,
)

function confirm() {
	if (!isValid.value) return
	emit('select', newOperation.value)
	reset()
	showDialog.value = false
}
function reset() {
	newOperation.value = {
		expression: expression(''),
	}
}
</script>

<template>
	<Dialog
		v-model:open="showDialog"
		@after-leave="reset"
		@close="!newOperation.expression.expression && (showDialog = false)"
		size="4xl"
		title="Custom Operation"
		:dismissible="!isDirty"
	>
		<div>
			<div class="flex flex-col gap-2">
				<ExpressionEditor
					class="h-[26rem]"
					v-model="newOperation.expression.expression"
					:column-options="props.columnOptions"
				/>
			</div>
			<div class="mt-2 flex items-center justify-between gap-2">
				<div></div>
				<div class="flex items-center gap-2">
					<Button label="Confirm" variant="solid" :disabled="!isValid" @click="confirm" />
				</div>
			</div>
		</div>
	</Dialog>
</template>
