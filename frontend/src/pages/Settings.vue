<template>
	<header class="sticky top-0 z-10 flex items-center justify-between bg-white px-5 py-2.5">
		<PageBreadcrumbs class="h-7" :items="[{ label: __('Settings') }]" />
		<div class="space-x-2.5">
			<Button
				:label="__('Update')"
				:disabled="updateDisabled"
				variant="solid"
				@click="store.update(configurables)"
			>
				<template #prefix>
					<CheckIcon class="w-4" />
				</template>
			</Button>
		</div>
	</header>
	<div class="flex flex-1 space-y-4 overflow-hidden bg-white px-6 py-2">
		<div class="-m-1 flex flex-1 flex-col space-y-6 overflow-y-auto p-1">
			<div class="rounded bg-white p-6 shadow">
				<div class="flex items-baseline">
					<div class="text-xl font-medium text-gray-700">{{ __('General') }}</div>
				</div>
				<div class="mt-4 flex flex-col space-y-8">
					<Setting
						:label="__('Max Query Result Limit')"
						:description="__('Maximum number of rows to be returned by a query. This is to prevent long running queries and memory issues.')"
					>
						<Input type="number" min="0" v-model="configurables.query_result_limit" />
						<div class="ml-2 text-gray-600">{{ __('Rows') }}</div>
					</Setting>

					<Setting
						:label="__('Cache Query Results For')"
						:description="__('Number of minutes to cache query results. This is to prevent accidental running of the same query multiple times.')"
					>
						<Input type="number" min="0" v-model="configurables.query_result_expiry" />
						<div class="ml-2 text-gray-600">{{ __('Minutes') }}</div>
					</Setting>

					<Setting
						:label="__('Fiscal Year Start')"
						:description="__('Start of the fiscal year. This is used to calculate fiscal year for date columns.')"
					>
						<DatePicker
							:placeholder="__('Select Date')"
							:value="configurables.fiscal_year_start"
							@change="configurables.fiscal_year_start = $event"
						/>
					</Setting>

					<Setting
						:label="__('Auto Execute Query')"
						:description="__('Automatically execute when tables, columns, or filters are changed.')"
					>
						<Input
							type="checkbox"
							v-model="configurables.auto_execute_query"
							:label="configurables.auto_execute_query ? __('Enabled') : __('Disabled')"
						/>
					</Setting>

					<Setting
						:label="__('Enable Query Reusability')"
						:description="__('Allow selecting query as a table in another query. Any query selected as a table will be appended as a sub query using CTE (Common Table Expression).')"
					>
						<Input
							type="checkbox"
							v-model="configurables.allow_subquery"
							:label="configurables.allow_subquery ? __('Enabled') : __('Disabled')"
						/>
					</Setting>
				</div>
			</div>

			<div class="rounded bg-white p-6 shadow">
				<div class="flex items-baseline">
					<div class="text-xl font-medium text-gray-700">{{ __('Notifications') }}</div>
				</div>
				<div class="mt-4 flex flex-col space-y-8">
					<Setting
						:label="__('Telegram Bot Token')"
						:description="__('Telegram bot token to send notifications to Telegram.')"
					>
						<Input
							type="password"
							v-model="configurables.telegram_api_token"
							:placeholder="__('Telegram Bot Token')"
						/>
					</Setting>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import DatePicker from '@/components/Controls/DatePicker.vue'
import PageBreadcrumbs from '@/components/PageBreadcrumbs.vue'
import Setting from '@/components/Setting.vue'
import settingsStore from '@/stores/settingsStore'
import { CheckIcon } from 'lucide-vue-next'
import { computed, ref, watchEffect } from 'vue'

const initialValues = {
	query_result_limit: 1000,
	query_result_expiry: 60,
	auto_execute_query: true,
	allow_subquery: true,
	fiscal_year_start: null,
	telegram_api_token: '',
}

const configurables = ref(initialValues)
const store = settingsStore()
watchEffect(() => {
	if (store.settings) {
		Object.keys(configurables.value).forEach((key) => {
			configurables.value[key] = store.settings[key]
		})
	} else {
		configurables.value = initialValues
	}
})
const updateDisabled = computed(() => {
	const local = configurables.value
	const remote = store.settings
	if (!local || !remote) return true
	return (
		// check if any value of local is different from remote
		Object.keys(local).find((key) => local[key] !== remote[key]) === undefined ||
		store.settings.loading
	)
})

document.title = __('Settings - Insights')
</script>
