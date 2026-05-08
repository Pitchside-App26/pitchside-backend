export type BodyType = 'saloon' | 'suv' | 'hatchback' | 'estate' | 'coupe' | 'convertible'
export type FuelType = 'petrol' | 'diesel' | 'electric' | 'hybrid' | 'phev'
export type TransmissionType = 'manual' | 'automatic'
export type FinanceType = 'pcp' | 'hp' | 'personal_loan'
export type DealStage =
  | 'listed'
  | 'buyer_found'
  | 'funds_in_escrow'
  | 'lender_contacted'
  | 'settlement_paid'
  | 'v5c_transferred'
  | 'pickup_arranged'
  | 'released'

export interface Lender {
  id: string
  name: string
  logo?: string
}

export interface Valuation {
  reg: string
  year: number
  make: string
  model: string
  trim: string
  colour: string
  mileage: number
  dealerOffer: number
  privateViaHandover: number
  estimatedLow: number
  estimatedHigh: number
  outstandingFinance: number
  lender: string
  financeType: FinanceType
}

export interface Listing {
  id: string
  reg: string
  year: number
  make: string
  model: string
  trim: string
  bodyType: BodyType
  fuel: FuelType
  transmission: TransmissionType
  colour: string
  mileage: number
  askingPrice: number
  dealerOffer: number
  outstandingFinance: number
  lender: string
  financeType: FinanceType
  location: string
  description: string
  photos: string[]
  coverPhoto: string
  viewCount: number
  saveCount: number
  daysListed: number
  sellerId: string
  sellerName: string
  sellerAvatar?: string
  hpiClean: boolean
  createdAt: string
}

export interface Deal {
  id: string
  listingId: string
  reg: string
  carName: string
  buyerName: string
  sellerName: string
  stage: DealStage
  value: number
  settlement: number
  walkAway: number
  updatedAt: string
  timeline: DealTimelineEvent[]
}

export interface DealTimelineEvent {
  stage: DealStage
  label: string
  completedAt?: string
  isCurrent?: boolean
}

export interface Message {
  id: string
  from: 'buyer' | 'seller'
  fromName: string
  text: string
  sentAt: string
}
