<script setup>
import { useStorage } from '@vueuse/core'
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import ProgressRing from './ProgressRing.vue'

const router = useRouter()
const showOnboarding = ref(false)
const steps = reactive([
	{
		title: __('Connect Your Data'),
		name: 'connect_data',
		description: __(
			"Insights needs access to your data to start analyzing it. Don't worry, we do not store your data."
		),
		primary_button: {
			label: __('Create Data Source'),
			action: () => router.push('/data-source#new'),
		},
	},
	{
		title: __('Build Your First Query'),
		name: 'build_query',
		description: __(
			"Let's introduce you to the query builder, where you'll be spending most of your time building queries."
		),
		primary_button: {
			label: __('Build Query'),
			action: () => router.push('/query#new'),
		},
	},
	{
		title: __('Create Your First Dashboard'),
		name: 'create_dashboard',
		description: __(
			'Organize your visualizations meaningfully by creating a dashboard for you and your team.'
		),
		primary_button: {
			label: __('Create Dashboard'),
			action: () => router.push('/dashboard#new'),
		},
	},
	{
		title: __('All set! 🎉'),
		name: 'all_set',
		description: __('You are all set to use Insights. We hope you enjoy using it!'),
		primary_button: {
			label: __('Close'),
			action: () => completeOnboarding(),
		},
	},
])

const initialOnboardingStatus = steps.reduce((acc, step) => ({ [step.name]: false }), {})
const onboarding = useStorage('insights:onboardingStatus', initialOnboardingStatus)

const currentStep = computed(() => {
	return steps.findIndex((step) => !onboarding.value[step.name])
})
function skipCurrentStep() {
	onboarding.value = { ...onboarding.value, [steps[currentStep.value].name]: true }
}
function completeOnboarding() {
	onboarding.value = { ...onboarding.value, all_set: true }
	showOnboarding.value = false
}
</script>

<template>
	<div v-if="!onboarding.all_set && currentStep < steps.length">
		<div class="flex items-center justify-between rounded bg-gray-50 px-4 py-3">
			<div class="flex items-center space-x-2">
				<ProgressRing
					class="text-gray-900"
					:progress="(currentStep / steps.length) * 100"
					:progressLabel="currentStep"
				/>
				<div>
					<div class="text-lg font-bold text-gray-900">{{ __('Get Started with Insights') }}</div>
					<div class="mt-1 text-gray-600">
						{{ __('Follow through a couple of steps to get yourself familiar with Insights.') }}
					</div>
				</div>
			</div>
			<div class="flex justify-end space-x-2">
				<Button variant="outline" iconLeft="x" @click="completeOnboarding">
					{{ __('Skip') }}
				</Button>
				<Button variant="solid" iconRight="arrow-right" @click="showOnboarding = true">
					{{ __('{0} step(s) left', [steps.length - currentStep]) }}
				</Button>
			</div>
		</div>
	</div>

	<Dialog
		v-if="!onboarding.all_set && currentStep < steps.length"
		v-model="showOnboarding"
		:options="{
			title: steps[currentStep].title,
			size: '2xl',
		}"
	>
		<template #body-content>
			<div class="flex flex-col items-center justify-center space-y-4">
				<div
					v-if="steps[currentStep].name !== 'all_set'"
					:key="steps[currentStep].name"
					class="flex w-full items-center justify-center overflow-hidden rounded shadow-md"
				>
					<video autoplay loop muted class="h-full w-full">
						<source
							v-if="steps[currentStep].name === 'connect_data'"
							src="../assets/add-data-source-new.mp4"
							type="video/mp4"
						/>
						<source
							v-if="steps[currentStep].name === 'build_query'"
							src="../assets/build-first-query-new.mp4"
							type="video/mp4"
						/>
						<source
							v-if="steps[currentStep].name === 'create_dashboard'"
							src="../assets/create-first-dashboard-new.mp4"
							type="video/mp4"
						/>
						{{ __('Your browser does not support the video tag.') }}
					</video>
				</div>
				<div class="">
					{{ steps[currentStep].description }}
				</div>
				<div class="flex w-full justify-end space-x-2">
					<Button
						v-if="steps[currentStep].name !== 'all_set'"
						variant="ghost"
						@click="skipCurrentStep"
					>
						{{ __('Skip') }}
					</Button>
					<Button variant="solid" @click="steps[currentStep].primary_button.action">
						{{ steps[currentStep].primary_button.label }}
					</Button>
				</div>
			</div>
		</template>
	</Dialog>
</template>
