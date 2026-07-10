<template>
	<div class="mt-40 h-full w-full">
		<div class="flex flex-col items-center justify-center">
			<p class="text-2xl font-semibold text-blue-600">404</p>
			<h1 class="mt-1 text-[48px] font-bold tracking-tight text-gray-900">{{ __('Not Found') }}</h1>
			<div class="text-xl font-light">{{ __('The page you are looking for does not exist.') }}</div>
			<router-link to="/" class="mt-2 text-lg text-blue-600 underline">
				{{ __('Go Back') }}
			</router-link>
		</div>
	</div>
</template>
