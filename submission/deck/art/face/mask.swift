// mask.swift <in.png> <out.png>: the person in a frame as a white-on-black mask (Apple's Vision, on this Mac).
import Vision
import AppKit
import CoreImage
let a = CommandLine.arguments
let img = CIImage(contentsOf: URL(fileURLWithPath: a[1]))!
let req = VNGeneratePersonSegmentationRequest()
req.qualityLevel = .accurate
req.outputPixelFormat = kCVPixelFormatType_OneComponent8
try VNImageRequestHandler(ciImage: img).perform([req])
let mask = CIImage(cvPixelBuffer: req.results!.first!.pixelBuffer)
let scaled = mask.transformed(by: CGAffineTransform(scaleX: img.extent.width / mask.extent.width, y: img.extent.height / mask.extent.height))
let cg = CIContext().createCGImage(scaled, from: img.extent)!
try NSBitmapImageRep(cgImage: cg).representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: a[2]))
print("mask", cg.width, cg.height)
