<script setup>
import { inject, reactive, ref } from 'vue'
const emit = defineEmits(['next'])

const selectedOption = ref(null)
const options = reactive([
	{
		title: __('ERPNext'),
		description: __('Connect to your ERPNext site'),
		img: 'ERPNextIcon.png',
	},
	{
		title: __('MariaDB'),
		description: __('Connect to MariaDB database'),
		img: 'MariaDBIcon.png',
	},
	{
		title: __('PostgreSQL'),
		description: __('Connect to PostgreSQL database'),
		img: 'PostgreSQLIcon.png',
	},
	{
		title: __('Spreadsheet'),
		description: __('Connect or Upload a spreadsheet'),
		img: 'SheetIcon.png',
	},
	{
		title: __('Sample Dataset'),
		description: __('Explore Insights with sample data'),
		img: 'SampleDataIcon.png',
	},
])

const $notify = inject('$notify')
const setupState = inject('setupState')
function validateAndContinue() {
	if (selectedOption.value === null) {
		$notify({
			title: __('Please select an option'),
			message: __('Please select an option to continue'),
			type: 'error',
		})
		return
	}

	if (selectedOption.value === 0) {
		setupState.sourceType = 'erpnext'
	} else if (selectedOption.value === 1) {
		setupState.sourceType = 'mariadb'
	} else if (selectedOption.value === 2) {
		setupState.sourceType = 'postgresql'
	} else if (selectedOption.value === 3) {
		setupState.sourceType = 'file'
	} else if (selectedOption.value === 4) {
		setupState.sourceType = 'sample'
	}

	emit('next')
}
</script>
<template>
	<div class="mt-6">
		<!-- card for each source (erpnext, database, file) -->
		<div class="grid grid-cols-2 gap-4 px-1">
			<div
				v-for="(option, index) in options"
				class="col-span-1 flex cursor-pointer items-center rounded border border-gray-300 px-4 py-3 transition-all"
				:class="
					selectedOption === index
						? ' border-gray-500 ring-2 ring-gray-400'
						: 'hover:border-gray-500'
				"
				@click="selectedOption = index"
			>
				<div v-if="option.img" class="mr-2 flex w-10 items-center justify-center">
					<img v-if="option.img === 'SheetIcon.png'" src="../assets/SheetIcon.png" />
					<img v-if="option.img === 'ERPNextIcon.png'" src="../assets/ERPNextIcon.png" />
					<img v-if="option.img === 'MariaDBIcon.png'" src="../assets/MariaDBIcon.png" />
					<img
						v-if="option.img === 'PostgreSQLIcon.png'"
						src="../assets/PostgreSQLIcon.png"
					/>
					<img
						v-if="option.img === 'SampleDataIcon.png'"
						src="../assets/SampleDataIcon.png"
					/>
				</div>
				<div>
					<div class="font-bold leading-6 text-gray-900">
						{{ option.title }}
					</div>
					<div class="text-sm text-gray-700">{{ option.description }}</div>
				</div>
			</div>
		</div>

		<div class="mt-6 flex justify-end space-x-3">
			<Button
				variant="solid"
				:disabled="selectedOption === null"
				@click="validateAndContinue"
			>
				{{ __('Continue') }}
			</Button>
		</div>
	</div>
</template>
